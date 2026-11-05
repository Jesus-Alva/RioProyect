"""API FastAPI para conversaciones seguras con agentes de Azure AI Foundry."""

import os
from functools import lru_cache
from typing import Any
from urllib.parse import quote

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel, Field

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


load_dotenv()

app = FastAPI()
bearer_scheme = HTTPBearer(auto_error=False)
ALLOWED_ROLES = {"directivo", "analista", "gerente", "bodega", "ti"}
AGENT_NAMES = {
    "directivo": "rio-directivo",
    "analista": "rio-analista",
    "gerente": "rio-gerente",
    "bodega": "rio-bodega",
    "ti": "rio-ti",
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    role: str
    conversation_id: str | None = None


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


@lru_cache(maxsize=8)
def get_jwks_client(tenant_id: str) -> PyJWKClient:
    encoded_tenant_id = quote(tenant_id, safe="")
    jwks_url = (
        "https://login.microsoftonline.com/"
        f"{encoded_tenant_id}/discovery/v2.0/keys"
    )
    return PyJWKClient(jwks_url)


def authenticate_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    
    # --- INICIO DEL BYPASS PARA DESARROLLO LOCAL ---
    if os.getenv("ENVIRONMENT", "development") == "development":
        return {
            # Le damos todos los roles para que puedas probar cualquiera desde Swagger
            "roles": ["directivo", "analista", "gerente", "bodega", "ti"],
            "oid": "usuario-de-prueba-123"
        }
    # --- FIN DEL BYPASS ---

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Se requiere un token Bearer válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant_id = os.getenv("ENTRA_TENANT_ID")
    audience = os.getenv("ENTRA_AUDIENCE")
    if not tenant_id or not audience:
        raise HTTPException(
            status_code=503,
            detail="La autenticación no está configurada.",
        )

    issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
    try:
        signing_key = get_jwks_client(tenant_id).get_signing_key_from_jwt(
            credentials.credentials
        )
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="El token de autenticación no es válido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return claims


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(
    request: ChatRequest,
    claims: dict[str, Any] = Depends(authenticate_user),
) -> dict[str, str]:
    role = request.role.lower()
    token_roles = claims.get("roles")
    if (
        role not in ALLOWED_ROLES
        or not isinstance(token_roles, list)
        or role not in token_roles
    ):
        raise HTTPException(
            status_code=422,
            detail="El rol solicitado no está autorizado para este usuario.",
        )

    user_id = claims.get("oid")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=401,
            detail="El token no identifica a un usuario válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
                or metadata.get("role") != role
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
                metadata={"owner": user_id, "role": role},
            )
            conversation_id = conversation.id

        response = openai_client.responses.create(
            conversation=conversation_id,
            extra_body={
                "agent_reference": {
                    "name": AGENT_NAMES[role],
                    "type": "agent_reference",
                },
                "structured_inputs": {"userFilter": role},
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR DE FOUNDRY: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail="No fue posible procesar la solicitud en Azure AI Foundry.",
        ) from None

    return {
        "conversation_id": conversation_id,
        "response": response.output_text,
    }
