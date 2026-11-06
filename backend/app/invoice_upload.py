"""Invoice upload processing and Azure integrations."""

import hashlib
import json
import logging
import math
import os
import re
import unicodedata
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.exceptions import AzureError, ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient, ContentSettings
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.database import InvoiceUpload
from backend.app.invoice_naming import generate_invoice_filename
from backend.scripts.seed_data import (
    field_confidence,
    field_value,
    invoice_date_value,
    invoice_to_search_document,
    invoice_total_value,
)


logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
INDEXED_ROLES = ["analista", "directivo", "gerente"]
DEFAULT_CONTAINER_NAME = "facturas-raw"
IMAGE_TYPES = {
    ".pdf": ("application/pdf", lambda content: content.startswith(b"%PDF-")),
    ".png": ("image/png", lambda content: content.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda content: content.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda content: content.startswith(b"\xff\xd8\xff")),
    ".tif": (
        "image/tiff",
        lambda content: content.startswith((b"II*\x00", b"MM\x00*")),
    ),
    ".tiff": (
        "image/tiff",
        lambda content: content.startswith((b"II*\x00", b"MM\x00*")),
    ),
    ".bmp": ("image/bmp", lambda content: content.startswith(b"BM")),
}


class InvoiceServiceError(Exception):
    """Raised when an external invoice operation returns an unusable result."""


def sanitize_filename(filename: str | None) -> str:
    safe_name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not safe_name or len(safe_name) > 255:
        raise HTTPException(
            status_code=422,
            detail="El archivo debe tener un nombre válido de hasta 255 caracteres.",
        )
    return safe_name


def validate_file_content(filename: str, content: bytes) -> str:
    extension = os.path.splitext(filename)[1].lower()
    file_type = IMAGE_TYPES.get(extension)
    if file_type is None or not file_type[1](content):
        raise HTTPException(
            status_code=415,
            detail="El archivo debe ser un PDF o una imagen compatible.",
        )
    return file_type[0]


def _reserve_upload(
    db: Session,
    content_hash: str,
    filename: str,
    content_type: str,
    branch: str,
    user_id: int,
) -> InvoiceUpload:
    upload = InvoiceUpload(
        document_hash=content_hash,
        original_filename=filename,
        content_type=content_type,
        branch=branch,
        status="processing",
        uploaded_by=user_id,
        review_reasons="[]",
    )
    db.add(upload)
    try:
        db.commit()
        db.refresh(upload)
        return upload
    except IntegrityError:
        db.rollback()

    existing = db.scalar(
        select(InvoiceUpload).where(InvoiceUpload.document_hash == content_hash)
    )
    if existing is None or existing.status != "failed":
        raise HTTPException(
            status_code=409,
            detail="Factura duplicada o carga ya en proceso.",
        ) from None

    claimed = db.execute(
        update(InvoiceUpload)
        .where(
            InvoiceUpload.id == existing.id,
            InvoiceUpload.status == "failed",
        )
        .values(
            original_filename=filename,
            content_type=content_type,
            branch=branch,
            uploaded_by=user_id,
            status="processing",
            review_reasons="[]",
        )
    )
    db.commit()
    if claimed.rowcount != 1:
        raise HTTPException(
            status_code=409,
            detail="Factura duplicada o carga ya en proceso.",
        ) from None
    db.refresh(existing)
    return existing


def _set_failed(db: Session, upload: InvoiceUpload) -> None:
    upload.status = "failed"
    db.commit()


def _save_review(
    db: Session,
    upload: InvoiceUpload,
    reasons: list[str],
    vendor_name: Any = None,
    invoice_date: Any = None,
    invoice_total: Any = None,
    vendor_confidence: float | None = None,
    total_confidence: float | None = None,
    possible_duplicate: bool = False,
) -> tuple[int, dict[str, Any]]:
    if possible_duplicate:
        reasons.append(
            "Coincidencia posible de proveedor, fecha y total; requiere revisión humana."
        )
    upload.status = "needs_review"
    upload.vendor_name = str(vendor_name).strip()[:255] if vendor_name else None
    upload.invoice_date = invoice_date
    upload.invoice_total = invoice_total
    upload.vendor_confidence = vendor_confidence
    upload.total_confidence = total_confidence
    upload.review_reasons = json.dumps(reasons, ensure_ascii=False)
    db.commit()
    db.refresh(upload)
    return 202, {
        "status": "needs_review",
        "detail": "Requiere revisión manual.",
        "review_id": upload.id,
        "branch": upload.branch,
        "filename": upload.generated_filename or upload.original_filename,
        "original_filename": upload.original_filename,
        "possible_duplicate": possible_duplicate,
    }


def _find_exact_duplicate(search_client: SearchClient, content_hash: str) -> bool:
    matches = search_client.search(
        search_text="*",
        filter=f"document_hash eq '{content_hash}'",
        select=["id"],
        top=1,
    )
    return next(iter(matches), None) is not None


def _normalize_vendor(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", normalized).split())


def _date_for_comparison(value: Any) -> str | None:
    normalized = invoice_date_value(value)
    if normalized is None:
        return None
    return normalized[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", normalized) else normalized


def _find_possible_duplicate(
    search_client: SearchClient,
    vendor_name: Any,
    invoice_date: Any,
    invoice_total: float,
) -> bool:
    comparable_date = _date_for_comparison(invoice_date)
    if comparable_date is None:
        return False
    escaped_date = comparable_date.replace("'", "''")
    candidates = search_client.search(
        search_text="*",
        filter=(
            f"invoice_date eq '{escaped_date}' and "
            f"invoice_total ge {invoice_total - 0.005} and "
            f"invoice_total le {invoice_total + 0.005}"
        ),
        select=["vendor_name", "invoice_date", "invoice_total"],
        top=1000,
    )
    normalized_vendor = _normalize_vendor(vendor_name)
    for candidate in candidates:
        candidate_date = _date_for_comparison(candidate.get("invoice_date"))
        try:
            candidate_total = float(candidate.get("invoice_total"))
        except (TypeError, ValueError):
            continue
        if (
            candidate_date == comparable_date
            and math.isclose(candidate_total, invoice_total, rel_tol=0, abs_tol=0.005)
            and _normalize_vendor(candidate.get("vendor_name")) == normalized_vendor
        ):
            return True
    return False


def _upload_original(
    blob_service: BlobServiceClient,
    content: bytes,
    content_hash: str,
    content_type: str,
    blob_name: str,
) -> str:
    container_name = (
        os.getenv("AZURE_STORAGE_CONTAINER_NAME") or DEFAULT_CONTAINER_NAME
    )
    container = blob_service.get_container_client(container_name)
    if not container.exists():
        try:
            container.create_container()
        except ResourceExistsError:
            pass

    blob = container.get_blob_client(blob_name)
    try:
        blob.upload_blob(
            content,
            overwrite=False,
            metadata={"sha256": content_hash, "retention_days": "90"},
            content_settings=ContentSettings(content_type=content_type),
        )
    except ResourceExistsError:
        properties = blob.get_blob_properties()
        if (properties.metadata or {}).get("sha256") != content_hash:
            raise InvoiceServiceError("El blob existente no coincide con su hash.")
    return blob_name


def _store_original(
    db: Session,
    upload: InvoiceUpload,
    blob_service: BlobServiceClient,
    content: bytes,
    content_hash: str,
    content_type: str,
    invoice_date: Any = None,
    vendor_name: Any = None,
    vendor_confidence: float | None = None,
) -> str:
    generated_filename = generate_invoice_filename(
        upload.original_filename,
        upload.branch,
        invoice_date,
        vendor_name,
        vendor_confidence,
        content_hash,
    )
    blob_name = f"invoices/{upload.branch}/{generated_filename}"
    upload.generated_filename = generated_filename
    upload.blob_name = _upload_original(
        blob_service, content, content_hash, content_type, blob_name
    )
    db.commit()
    return generated_filename


def process_invoice_upload(
    content: bytes,
    filename: str,
    content_type: str,
    branch: str,
    user_id: int,
    db: Session,
) -> tuple[int, dict[str, Any]]:
    document_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    blob_endpoint = os.getenv("AZURE_STORAGE_BLOB_URL")
    if not document_endpoint or not search_endpoint or not blob_endpoint:
        raise HTTPException(
            status_code=503,
            detail="La carga de facturas no está configurada en el servidor.",
        )

    content_hash = hashlib.sha256(content).hexdigest()
    upload = _reserve_upload(
        db, content_hash, filename, content_type, branch, user_id
    )
    credential = None
    search_client = None
    blob_service = None
    document_client = None
    operation = "autenticar con Azure"
    try:
        credential = DefaultAzureCredential()
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rio-claro-invoices")
        operation = "conectar con Azure AI Search"
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=credential,
        )
        operation = "verificar duplicado en Azure AI Search"
        if _find_exact_duplicate(search_client, content_hash):
            upload.status = "duplicate"
            db.commit()
            raise HTTPException(status_code=409, detail="Factura duplicada.")

        operation = "analizar documento con Document Intelligence"
        document_client = DocumentIntelligenceClient(
            endpoint=document_endpoint,
            credential=credential,
        )
        poller = document_client.begin_analyze_document(
            "prebuilt-invoice",
            body=content,
        )
        result = poller.result()
        operation = "conectar con Blob Storage"
        blob_service = BlobServiceClient(
            account_url=blob_endpoint,
            credential=credential,
        )
        documents = result.documents or []
        if not documents:
            operation = "guardar archivo para revisión en Blob Storage"
            generated_filename = _store_original(
                db,
                upload,
                blob_service,
                content,
                content_hash,
                content_type,
            )
            status_code, response = _save_review(
                db,
                upload,
                ["Document Intelligence no detectó una factura."],
            )
            return status_code, response
        if len(documents) != 1:
            operation = "guardar archivo para revisión en Blob Storage"
            generated_filename = _store_original(
                db,
                upload,
                blob_service,
                content,
                content_hash,
                content_type,
            )
            status_code, response = _save_review(
                db,
                upload,
                ["El archivo contiene varias facturas; requiere revisión manual."],
            )
            return status_code, response

        analyzed_document = documents[0]
        fields = analyzed_document.fields or {}
        vendor_name = field_value(fields, "VendorName")
        raw_total = field_value(fields, "InvoiceTotal")
        invoice_date = invoice_date_value(field_value(fields, "InvoiceDate"))
        try:
            vendor_confidence = field_confidence(fields, "VendorName")
            total_confidence = field_confidence(fields, "InvoiceTotal")
        except (TypeError, ValueError):
            vendor_confidence = None
            total_confidence = None

        operation = "guardar factura en Blob Storage"
        generated_filename = _store_original(
            db,
            upload,
            blob_service,
            content,
            content_hash,
            content_type,
            invoice_date,
            vendor_name,
            vendor_confidence,
        )
        try:
            search_document, reasons = invoice_to_search_document(
                analyzed_document,
                generated_filename,
                result.content,
                content_hash,
                1,
                INDEXED_ROLES,
                branch,
            )
        except (ArithmeticError, TypeError, ValueError):
            search_document, reasons = None, [
                "Document Intelligence devolvió datos que requieren revisión."
            ]
        if search_document is None:
            status_code, response = _save_review(
                db,
                upload,
                reasons,
                vendor_name=vendor_name,
                invoice_date=invoice_date,
                vendor_confidence=vendor_confidence,
                total_confidence=total_confidence,
            )
            return status_code, response

        operation = "buscar factura duplicada en Azure AI Search"
        normalized_total = invoice_total_value(raw_total)
        possible_duplicate = _find_possible_duplicate(
            search_client,
            vendor_name,
            invoice_date,
            normalized_total,
        )
        if possible_duplicate:
            status_code, response = _save_review(
                db,
                upload,
                [],
                vendor_name=vendor_name,
                invoice_date=invoice_date,
                invoice_total=normalized_total,
                vendor_confidence=vendor_confidence,
                total_confidence=total_confidence,
                possible_duplicate=True,
            )
            return status_code, response

        operation = "indexar factura en Azure AI Search"
        search_results = search_client.upload_documents(documents=[search_document])
        failed_results = [
            result for result in search_results if not result.succeeded
        ]
        if not search_results or failed_results:
            error_codes = [
                getattr(result, "error_code", None) for result in failed_results
            ]
            logger.error(
                "Azure AI Search rejected invoice upload: error_codes=%s",
                error_codes,
            )
            raise InvoiceServiceError("Azure AI Search no aceptó el documento.")

        upload.status = "indexed"
        upload.vendor_name = str(vendor_name).strip()[:255]
        upload.invoice_date = invoice_date
        upload.invoice_total = normalized_total
        upload.vendor_confidence = vendor_confidence
        upload.total_confidence = total_confidence
        db.commit()
        return 201, {
            "status": "indexed",
            "detail": "Factura guardada con éxito.",
            "branch": branch,
            "filename": generated_filename,
            "original_filename": upload.original_filename,
        }
    except HTTPException as error:
        if error.status_code == 409 and upload.status == "processing":
            upload.status = "duplicate"
            db.commit()
        raise
    except (AzureError, InvoiceServiceError) as error:
        status_code = 502
        detail = "No fue posible procesar o guardar la factura."
        logger.error(
            (
                "Invoice upload failed: operation=%s exception=%s "
                "status_code=%s error_code=%s"
            ),
            operation,
            type(error).__name__,
            getattr(error, "status_code", None),
            getattr(error, "error_code", None),
        )
        if isinstance(error, InvoiceServiceError):
            logger.error("Invoice upload service detail: %s", error)
        if (
            isinstance(error, AzureError)
            and "Blob Storage" in operation
            and getattr(error, "status_code", None) == 403
            and getattr(error, "error_code", None)
            == "AuthorizationPermissionMismatch"
        ):
            status_code = 503
            detail = (
                "La identidad autenticada no pudo escribir en el contenedor de "
                "facturas. Verifica que tenga Storage Blob Data Contributor en la "
                "cuenta o contenedor de almacenamiento configurado."
            )
        _set_failed(db, upload)
        raise HTTPException(
            status_code=status_code,
            detail=detail,
        ) from None
    finally:
        for client in (document_client, search_client, blob_service):
            if client is not None:
                client.close()
        if credential is not None:
            credential.close()


def list_invoice_reviews(user: dict[str, Any], db: Session) -> list[dict[str, Any]]:
    query = select(InvoiceUpload).where(InvoiceUpload.status == "needs_review")
    if user["role"] != "admin":
        query = query.where(InvoiceUpload.branch.in_(user["branches"]))
    uploads = db.scalars(
        query.order_by(InvoiceUpload.created_at.desc(), InvoiceUpload.id.desc()).limit(
            200
        )
    )
    return [
        {
            "id": upload.id,
            "filename": upload.generated_filename or upload.original_filename,
            "original_filename": upload.original_filename,
            "branch": upload.branch,
            "vendor_name": upload.vendor_name,
            "invoice_date": upload.invoice_date,
            "invoice_total": upload.invoice_total,
            "vendor_confidence": upload.vendor_confidence,
            "total_confidence": upload.total_confidence,
            "reasons": json.loads(upload.review_reasons),
            "created_at": (
                upload.created_at.isoformat() if upload.created_at else None
            ),
        }
        for upload in uploads
    ]
