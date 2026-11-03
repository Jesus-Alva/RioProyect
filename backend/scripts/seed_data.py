"""Extrae facturas locales y agrega al índice solo documentos confiables y autorizados."""

import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "invoices"
DEFAULT_ACCESS_MANIFEST = (
    PROJECT_ROOT / "backend" / "config" / "invoice-access.example.json"
)
DEFAULT_REVIEW_REPORT = PROJECT_ROOT / "data" / "needs_review.jsonl"
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
MIN_CONFIDENCE = 0.8


def load_access_manifest(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el manifiesto de acceso: {path}")

    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("El manifiesto debe ser un objeto JSON por nombre de archivo.")

    permissions: dict[str, list[str]] = {}
    for filename, roles in manifest.items():
        if (
            not isinstance(filename, str)
            or not filename.strip()
            or not isinstance(roles, list)
            or not roles
            or any(not isinstance(role, str) or not role.strip() for role in roles)
        ):
            raise ValueError(
                "Cada entrada del manifiesto debe mapear un nombre de archivo "
                "a una lista no vacía de roles."
            )
        permissions[filename] = sorted({role.strip() for role in roles})
    return permissions


def field_value(document_fields: dict[str, Any], name: str) -> Any:
    field = document_fields.get(name)
    return None if field is None else field.value


def field_confidence(document_fields: dict[str, Any], name: str) -> float | None:
    field = document_fields.get(name)
    if field is None or field.confidence is None:
        return None
    confidence = float(field.confidence)
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        return None
    return confidence


def get_review_reasons(document_fields: dict[str, Any]) -> list[str]:
    reasons = []
    for field_name in ("VendorName", "InvoiceTotal"):
        confidence = field_confidence(document_fields, field_name)
        if confidence is None:
            reasons.append(f"{field_name}: falta el campo o su confianza")
        elif confidence < MIN_CONFIDENCE:
            reasons.append(
                f"{field_name}: confianza {confidence:.3f} menor que {MIN_CONFIDENCE}"
            )
        elif field_value(document_fields, field_name) is None:
            reasons.append(f"{field_name}: falta el valor")
        elif field_name == "VendorName" and not str(
            field_value(document_fields, field_name)
        ).strip():
            reasons.append(f"{field_name}: el valor está vacío")
    return reasons


def invoice_total_value(value: Any) -> float:
    amount = value.get("amount") if isinstance(value, dict) else getattr(value, "amount", value)
    decimal_amount = Decimal(str(amount))
    if not decimal_amount.is_finite():
        raise ValueError("El total no es un número finito.")
    total = float(decimal_amount)
    if not math.isfinite(total):
        raise ValueError("El total excede el rango numérico permitido.")
    return total


def invoice_date_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def make_document_id(content_hash: str, document_number: int) -> str:
    raw_id = f"{content_hash}-{document_number}".encode("utf-8")
    return hashlib.sha256(raw_id).hexdigest()


def append_review_record(
    report_path: Path, filename: str, reasons: list[str], content_hash: str
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "document_filename": filename,
        "document_hash": content_hash,
        "status": "needs_review",
        "reasons": reasons,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    with report_path.open("a", encoding="utf-8") as report:
        report.write(json.dumps(record, ensure_ascii=False) + "\n")


def invoice_to_search_document(
    document: Any,
    filename: str,
    content_hash: str,
    document_number: int,
    role_ids: list[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    fields = document.fields or {}
    reasons = get_review_reasons(fields)
    if reasons:
        return None, reasons

    vendor_name = field_value(fields, "VendorName")
    total = field_value(fields, "InvoiceTotal")
    invoice_date = field_value(fields, "InvoiceDate")
    try:
        normalized_total = invoice_total_value(total)
    except (ArithmeticError, TypeError, ValueError) as error:
        return None, [f"InvoiceTotal: valor inválido ({error})"]

    return (
        {
            "id": make_document_id(content_hash, document_number),
            "document_filename": filename,
            "vendor_name": str(vendor_name),
            "invoice_total": normalized_total,
            "invoice_date": invoice_date_value(invoice_date),
            "security_id": role_ids,
            "product_names": [],
        },
        [],
    )


def main() -> int:
    di_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not di_endpoint or not search_endpoint:
        print(
            "Error: configura AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT y "
            "AZURE_SEARCH_ENDPOINT.",
            file=sys.stderr,
        )
        return 1

    input_dir = Path(os.getenv("INVOICE_INPUT_DIR", str(DEFAULT_INPUT_DIR)))
    manifest_path = Path(
        os.getenv("INVOICE_ACCESS_MANIFEST_PATH", str(DEFAULT_ACCESS_MANIFEST))
    )
    review_report = Path(
        os.getenv("NEEDS_REVIEW_REPORT_PATH", str(DEFAULT_REVIEW_REPORT))
    )
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "rio-claro-invoices")

    if not input_dir.is_dir():
        print(f"Error: no existe la carpeta de facturas: {input_dir}", file=sys.stderr)
        return 1

    try:
        access_manifest = load_access_manifest(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Error en el manifiesto de acceso: {error}", file=sys.stderr)
        return 1

    invoice_files = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not invoice_files:
        print(f"No se encontraron facturas compatibles en {input_dir}.")
        return 0

    credential = DefaultAzureCredential()
    indexed_count = 0
    review_count = 0
    error_count = 0

    try:
        document_client = DocumentIntelligenceClient(
            endpoint=di_endpoint, credential=credential
        )
        search_client = SearchClient(
            endpoint=search_endpoint, index_name=index_name, credential=credential
        )
        for invoice_path in invoice_files:
            content = invoice_path.read_bytes()
            content_hash = hashlib.sha256(content).hexdigest()
            role_ids = access_manifest.get(invoice_path.name)
            if not role_ids:
                reason = ["No hay roles autorizados para este archivo en el manifiesto."]
                append_review_record(
                    review_report, invoice_path.name, reason, content_hash
                )
                print(f"{invoice_path.name}: needs_review (sin security_id).")
                review_count += 1
                continue

            try:
                poller = document_client.begin_analyze_document(
                    "prebuilt-invoice", body=content
                )
                result = poller.result()
            except AzureError as error:
                print(
                    f"{invoice_path.name}: error de Document Intelligence: {error}",
                    file=sys.stderr,
                )
                error_count += 1
                continue

            analyzed_documents = result.documents or []
            if not analyzed_documents:
                append_review_record(
                    review_report,
                    invoice_path.name,
                    ["Document Intelligence no detectó una factura."],
                    content_hash,
                )
                print(f"{invoice_path.name}: needs_review (sin factura detectada).")
                review_count += 1
                continue

            for document_number, analyzed_document in enumerate(
                analyzed_documents, start=1
            ):
                search_document, reasons = invoice_to_search_document(
                    analyzed_document,
                    invoice_path.name,
                    content_hash,
                    document_number,
                    role_ids,
                )
                if search_document is None:
                    append_review_record(
                        review_report, invoice_path.name, reasons, content_hash
                    )
                    print(
                        f"{invoice_path.name}: needs_review "
                        f"({' ; '.join(reasons)})."
                    )
                    review_count += 1
                    continue

                try:
                    results = search_client.upload_documents(
                        documents=[search_document]
                    )
                except AzureError as error:
                    print(
                        f"{invoice_path.name}: error de Azure AI Search: {error}",
                        file=sys.stderr,
                    )
                    error_count += 1
                    continue

                if not results or not results[0].succeeded:
                    failure = (
                        "Azure AI Search no devolvió resultado de indexación."
                        if not results
                        else results[0].error_message
                    )
                    print(
                        f"{invoice_path.name}: no se pudo indexar: {failure}",
                        file=sys.stderr,
                    )
                    error_count += 1
                    continue

                print(f"{invoice_path.name}: indexada correctamente.")
                indexed_count += 1
    except (AzureError, OSError, ValueError) as error:
        print(f"Error durante la ingesta: {error}", file=sys.stderr)
        error_count += 1
    finally:
        credential.close()

    print(
        f"Resumen: {indexed_count} indexadas, {review_count} requieren revisión, "
        f"{error_count} errores."
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
