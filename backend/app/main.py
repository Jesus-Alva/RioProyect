"""API FastAPI para conversaciones seguras con agentes de Azure AI Foundry."""

from contextlib import asynccontextmanager
import os
from functools import lru_cache
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from backend.app.auth import authenticate_user, router as auth_router
from backend.app.database import initialize_database
from backend.app.roles import AGENT_NAMES, ADMIN_ROLE, OPERATIONAL_ROLES
from backend.app.security import validate_jwt_configuration


load_dotenv()


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


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    agent_role: Literal["directivo", "analista", "gerente", "bodega", "ti"] | None = None


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(
    request: ChatRequest,
    user: dict[str, Any] = Depends(authenticate_user),
) -> dict[str, str]:
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
                metadata={"owner": user_id, "role": agent_role},
            )
            conversation_id = conversation.id

        response = openai_client.responses.create(
            conversation=conversation_id,
            extra_body={
                "agent_reference": {
                    "name": AGENT_NAMES[agent_role],
                    "type": "agent_reference",
                },
                "structured_inputs": {"userFilter": agent_role},
            },
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No fue posible procesar la solicitud en Azure AI Foundry.",
        ) from None

    return {
        "conversation_id": conversation_id,
        "response": response.output_text,
    }
