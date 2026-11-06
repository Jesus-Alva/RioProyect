"""API FastAPI para conversaciones seguras con agentes de Azure AI Foundry."""

from contextlib import asynccontextmanager
import hashlib
import logging
import math
import os
from functools import lru_cache
from typing import Any, Literal
import unicodedata
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

from backend.app.auth import authenticate_user, router as auth_router
from backend.app.branches import BRANCHES, normalize_branches
from backend.app.database import InvoiceUpload, get_db, initialize_database
from backend.app.invoice_upload import (
    MAX_UPLOAD_BYTES,
    decide_invoice_review,
    get_invoice_review_preview,
    list_invoice_reviews,
    process_invoice_upload,
    sanitize_filename,
    validate_file_content,
)
from backend.app.roles import AGENT_NAMES, ADMIN_ROLE, OPERATIONAL_ROLES
from backend.app.security import validate_jwt_configuration


load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_jwt_configuration()
    initialize_database()
    yield


app = FastAPI(lifespan=lifespan)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)

Branch = Literal[
    "guadalajara",
    "zapopan",
    "leon",
    "queretaro",
    "aguascalientes",
]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    agent_role: Literal["directivo", "analista", "gerente", "bodega", "ti"] | None = None
    branches: list[Branch] = Field(min_length=1)

    @field_validator("branches")
    @classmethod
    def validate_branches(cls, value: list[Branch]) -> list[Branch]:
        return normalize_branches(value)


class InventoryMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    producto: str = Field(min_length=1, max_length=120)
    cantidad: int = Field(strict=True, gt=0, le=1_000_000)
    branch: Branch

    @field_validator("producto", mode="before")
    @classmethod
    def normalize_product_name(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("El nombre del producto debe ser texto.")
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Escribe el nombre del producto.")
        return normalized


@lru_cache(maxsize=1)
def get_project_client() -> AIProjectClient:
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT no está configurado.")
    return AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )


@lru_cache(maxsize=1)
def get_openai_client() -> Any:
    return get_project_client().get_openai_client()


def build_branch_filter(role: str, branches: list[str]) -> str:
    if role not in OPERATIONAL_ROLES:
        raise ValueError("El filtro requiere un rol operativo.")
    branch_filter = ",".join(normalize_branches(branches))
    return (
        f"security_id/any(g: search.in(g, '{role}')) and "
        f"search.in(branch, '{branch_filter}', ',')"
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/director/sales-report")
def director_sales_report(
    user: dict[str, Any] = Depends(authenticate_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if user["role"] != "directivo":
        raise HTTPException(
            status_code=403,
            detail="Solo Directivo puede consultar el reporte de facturas.",
        )

    authorized_branches = normalize_branches(user["branches"])
    aggregates = db.execute(
        select(
            InvoiceUpload.branch,
            func.count(InvoiceUpload.id),
            func.count(InvoiceUpload.invoice_total),
            func.sum(InvoiceUpload.invoice_total),
        )
        .where(
            InvoiceUpload.branch.in_(authorized_branches),
            InvoiceUpload.status.in_(("indexed", "approved")),
        )
        .group_by(InvoiceUpload.branch)
    ).all()
    totals_by_branch = {
        branch: {
            "invoice_count": invoice_count,
            "invoices_with_total": invoices_with_total,
            "total": float(total or 0),
        }
        for branch, invoice_count, invoices_with_total, total in aggregates
    }

    return {
        "currency": "MXN",
        "period": "all_time",
        "included_statuses": ["indexed", "approved"],
        "branches": [
            {
                "branch": branch,
                **totals_by_branch.get(
                    branch,
                    {
                        "invoice_count": 0,
                        "invoices_with_total": 0,
                        "total": 0,
                    },
                ),
            }
            for branch in BRANCHES
            if branch in authorized_branches
        ],
    }


@app.post("/api/invoices/upload")
def upload_invoice(
    file: UploadFile = File(...),
    branch: Branch = Form(...),
    user: dict[str, Any] = Depends(authenticate_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    if user["role"] != "analista":
        raise HTTPException(
            status_code=403,
            detail="Solo Analista puede cargar facturas.",
        )
    if branch not in user["branches"]:
        raise HTTPException(
            status_code=403,
            detail="La sucursal no está asignada a tu cuenta.",
        )

    filename = sanitize_filename(file.filename)
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="El archivo no puede superar 20 MB.",
        )
    if not content:
        raise HTTPException(
            status_code=422,
            detail="El archivo está vacío.",
        )
    content_type = validate_file_content(filename, content)
    status_code, payload = process_invoice_upload(
        content=content,
        filename=filename,
        content_type=content_type,
        branch=branch,
        user_id=user["id"],
        db=db,
    )
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/api/invoices/reviews")
def invoice_reviews(
    user: dict[str, Any] = Depends(authenticate_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if user["role"] not in {"analista", ADMIN_ROLE}:
        raise HTTPException(
            status_code=403,
            detail="Solo Analista o administrador puede consultar revisiones.",
        )
    return {"items": list_invoice_reviews(user, db)}


class InvoiceReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "decline"]


@app.get("/api/invoices/reviews/{review_id}/preview")
def invoice_review_preview(
    review_id: int,
    user: dict[str, Any] = Depends(authenticate_user),
    db: Session = Depends(get_db),
) -> Response:
    if user["role"] not in {"analista", ADMIN_ROLE}:
        raise HTTPException(
            status_code=403,
            detail="Solo Analista o administrador puede consultar revisiones.",
        )
    content, content_type, filename = get_invoice_review_preview(
        review_id, user, db
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.patch("/api/invoices/reviews/{review_id}")
def resolve_invoice_review(
    review_id: int,
    payload: InvoiceReviewDecision,
    user: dict[str, Any] = Depends(authenticate_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if user["role"] not in {"analista", ADMIN_ROLE}:
        raise HTTPException(
            status_code=403,
            detail="Solo Analista o administrador puede resolver revisiones.",
        )
    return decide_invoice_review(
        review_id=review_id,
        decision=payload.decision,
        user=user,
        db=db,
    )


@app.get("/api/inventory")
def inventory(
    user: dict[str, Any] = Depends(authenticate_user),
) -> dict[str, Any]:
    if user["role"] != "bodega":
        raise HTTPException(
            status_code=403,
            detail="Solo Bodega puede consultar el inventario.",
        )

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar el inventario.",
        )
    index_name = os.getenv(
        "AZURE_SEARCH_INVENTORY_INDEX_NAME", "inventario-index"
    )
    credential = None
    try:
        credential = DefaultAzureCredential()
        client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential,
        )
        results = client.search(
            search_text="*",
            filter=build_branch_filter("bodega", user["branches"]),
            select=["producto", "cantidad", "branch"],
        )
        items = []
        for result in results:
            branch = result.get("branch")
            if branch not in user["branches"]:
                continue
            items.append(
                {
                    "producto": result.get("producto"),
                    "cantidad": result.get("cantidad"),
                    "branch": branch,
                }
            )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar el inventario.",
        ) from None
    finally:
        if credential is not None:
            credential.close()

    return {"branches": user["branches"], "items": items}


def normalize_inventory_product(product: str) -> str:
    decomposed = unicodedata.normalize("NFKD", product.casefold())
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.split())


def find_inventory_product(
    client: SearchClient,
    branch: str,
    normalized_product: str,
) -> dict[str, Any] | None:
    results = client.search(
        search_text="*",
        filter=build_branch_filter("bodega", [branch]),
        select=["id", "producto", "cantidad", "branch", "security_id"],
        top=1000,
    )
    return next(
        (
            dict(result)
            for result in results
            if result.get("branch") == branch
            and normalize_inventory_product(str(result.get("producto", "")))
            == normalized_product
        ),
        None,
    )


@app.post("/api/inventory")
def mutate_inventory(
    payload: InventoryMutationRequest,
    user: dict[str, Any] = Depends(authenticate_user),
) -> dict[str, Any]:
    if user["role"] != "bodega":
        raise HTTPException(
            status_code=403,
            detail="Solo Bodega puede registrar o actualizar inventario.",
        )
    if payload.branch not in user["branches"]:
        raise HTTPException(
            status_code=403,
            detail="La sucursal no está asignada a tu cuenta.",
        )

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        raise HTTPException(
            status_code=502,
            detail="No fue posible actualizar el inventario.",
        )

    inventory_index_name = os.getenv(
        "AZURE_SEARCH_INVENTORY_INDEX_NAME", "inventario-index"
    )
    invoice_index_name = os.getenv(
        "AZURE_SEARCH_INDEX_NAME", "rio-claro-invoices"
    )
    index_names = tuple(dict.fromkeys((inventory_index_name, invoice_index_name)))
    credential = None
    clients: dict[str, SearchClient] = {}
    written_updates: list[tuple[str, dict[str, Any], dict[str, Any] | None]] = []
    rollback_failed = False
    try:
        credential = DefaultAzureCredential()
        for index_name in index_names:
            clients[index_name] = SearchClient(
                endpoint=endpoint,
                index_name=index_name,
                credential=credential,
            )

        normalized_product = normalize_inventory_product(payload.producto)
        existing_by_index = {
            index_name: find_inventory_product(
                client, payload.branch, normalized_product
            )
            for index_name, client in clients.items()
        }
        source_document = (
            existing_by_index.get(inventory_index_name)
            or next(
                (document for document in existing_by_index.values() if document),
                None,
            )
        )
        current_quantity = float(source_document.get("cantidad", 0) or 0) if source_document else 0.0
        if not math.isfinite(current_quantity):
            raise ValueError("La cantidad registrada para el producto no es válida.")
        updated_quantity = current_quantity + payload.cantidad
        product_name = (
            str(source_document.get("producto", payload.producto))
            if source_document
            else payload.producto
        )
        product_key = hashlib.sha256(normalized_product.encode("utf-8")).hexdigest()[:24]
        fallback_id = f"{payload.branch}-{product_key}"

        try:
            for index_name, client in clients.items():
                existing = existing_by_index[index_name]
                document = {
                    "id": str(existing.get("id")) if existing else fallback_id,
                    "producto": product_name,
                    "cantidad": updated_quantity,
                    "branch": payload.branch,
                    "security_id": ["bodega"],
                }
                results = client.merge_or_upload_documents(documents=[document])
                if not results or not results[0].succeeded:
                    raise RuntimeError(
                        f"Azure AI Search no confirmó la actualización de {index_name}."
                    )
                written_updates.append((index_name, document, existing))
        except Exception:
            for index_name, document, existing in reversed(written_updates):
                try:
                    if existing:
                        clients[index_name].merge_documents(
                            documents=[
                                {
                                    "id": existing["id"],
                                    "cantidad": existing.get("cantidad", 0),
                                }
                            ]
                        )
                    else:
                        clients[index_name].delete_documents(
                            documents=[{"id": document["id"]}]
                        )
                except Exception:
                    rollback_failed = True
                    logger.exception(
                        "No fue posible revertir una escritura parcial de inventario en %s.",
                        index_name,
                    )
            raise
    except HTTPException:
        raise
    except Exception:
        logger.exception("Falló la actualización del inventario en Azure AI Search.")
        raise HTTPException(
            status_code=502,
            detail=(
                "La actualización quedó incompleta entre los índices. Actualiza el inventario antes de volver a intentarlo."
                if rollback_failed
                else "No fue posible actualizar el inventario. Inténtalo de nuevo."
            ),
        ) from None
    finally:
        for client in clients.values():
            client.close()
        if credential is not None:
            credential.close()

    operation = "increased" if source_document else "created"
    return {
        "operation": operation,
        "producto": product_name,
        "cantidad_agregada": payload.cantidad,
        "cantidad_total": updated_quantity,
        "branch": payload.branch,
    }


@app.post("/api/chat")
def chat(
    request: ChatRequest,
    user: dict[str, Any] = Depends(authenticate_user),
) -> dict[str, Any]:
    selected_branches = request.branches
    if not set(selected_branches).issubset(set(user["branches"])):
        raise HTTPException(
            status_code=403,
            detail="La selección contiene una sucursal no asignada a tu cuenta.",
        )

    if user["role"] == ADMIN_ROLE:
        if request.agent_role is None:
            raise HTTPException(
                status_code=422,
                detail="El administrador debe seleccionar un agente operativo.",
            )
        agent_role = request.agent_role
    else:
        if request.agent_role is not None and request.agent_role != user["role"]:
            raise HTTPException(
                status_code=403,
                detail="No puedes consultar un agente ajeno a tu rol.",
            )
        agent_role = user["role"]

    if agent_role not in OPERATIONAL_ROLES:
        raise HTTPException(
            status_code=403,
            detail="El agente solicitado no está autorizado.",
        )

    user_id = str(user["id"])
    branch_metadata = ",".join(selected_branches)

    try:
        openai_client = get_openai_client()
        user_message = {
            "type": "message",
            "role": "user",
            "content": request.message,
        }
        if request.conversation_id:
            conversation_id = request.conversation_id
            conversation = openai_client.conversations.retrieve(conversation_id)
            metadata = conversation.metadata or {}
            if (
                metadata.get("owner") != user_id
                or metadata.get("role") != agent_role
                or metadata.get("branches") != branch_metadata
            ):
                raise HTTPException(
                    status_code=404,
                    detail="No se encontró la conversación.",
                )
            openai_client.conversations.items.create(
                conversation_id=conversation_id,
                items=[user_message],
            )
        else:
            conversation = openai_client.conversations.create(
                items=[user_message],
                metadata={
                    "owner": user_id,
                    "role": agent_role,
                    "branches": branch_metadata,
                },
            )
            conversation_id = conversation.id

        response = openai_client.responses.create(
            conversation=conversation_id,
            extra_body={
                "agent_reference": {
                    "name": AGENT_NAMES[agent_role],
                    "type": "agent_reference",
                },
                "structured_inputs": {
                    "userFilter": agent_role,
                    "branchFilter": ",".join(selected_branches),
                },
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Falló la consulta del agente de Azure AI Foundry.")
        raise HTTPException(
            status_code=502,
            detail="No fue posible procesar la solicitud en Azure AI Foundry.",
        ) from None

    return {
        "conversation_id": conversation_id,
        "response": response.output_text,
        "branches": selected_branches,
    }
