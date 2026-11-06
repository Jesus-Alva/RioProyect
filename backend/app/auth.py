import re
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.exc import UnknownHashError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.branches import BRANCHES, normalize_branches
from backend.app.database import User, get_db
from backend.app.roles import ADMIN_ROLE, ALL_ROLES
from backend.app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


OperationalRole = Literal["directivo", "analista", "gerente", "bodega", "ti"]
Branch = Literal[
    "guadalajara",
    "zapopan",
    "leon",
    "queretaro",
    "aguascalientes",
]
BranchList = list[Branch]
bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/api/auth", tags=["authentication"])


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    role: OperationalRole
    branch: Branch

    @field_validator("password")
    @classmethod
    def validate_password_format(cls, value: str) -> str:
        if not any(character.isupper() for character in value):
            raise ValueError("La contraseña debe incluir al menos una letra mayúscula.")
        if not re.search(r"[0-9]", value):
            raise ValueError("La contraseña debe incluir al menos un número.")
        if not any(not character.isalnum() and not character.isspace() for character in value):
            raise ValueError("La contraseña debe incluir al menos un carácter especial.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Ingresa un correo electrónico válido.")
        return normalized


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Ingresa un correo electrónico válido.")
        return normalized


class UserAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: OperationalRole | None = None
    branches: BranchList | None = Field(default=None, min_length=1)
    is_active: bool | None = None

    @field_validator("branches")
    @classmethod
    def validate_branches(cls, value: BranchList | None) -> BranchList | None:
        if value is None:
            return value
        return normalize_branches(value)


def user_response(user: User) -> dict:
    raw_branches = list(BRANCHES) if user.role == ADMIN_ROLE else user.branches
    try:
        assigned_branches = normalize_branches(raw_branches) if raw_branches else []
    except (TypeError, ValueError):
        assigned_branches = []
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "requested_role": user.requested_role,
        "branches": assigned_branches,
        "requested_branches": list(user.requested_branches or []),
        "status": user.status,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def authenticate_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="El token de autenticación no es válido o expiró.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un token Bearer.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = decode_access_token(credentials.credentials)
        user_id = int(claims["sub"])
        role = claims["role"]
        claimed_branches = claims["branches"]
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise unauthorized from None
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La autenticación no está configurada.",
        ) from None

    if user_id < 1 or role not in ALL_ROLES:
        raise unauthorized

    user = db.get(User, user_id)
    if (
        user is None
        or user.status != "active"
        or not user.is_active
        or user.role != role
    ):
        raise unauthorized
    raw_branches = list(BRANCHES) if role == ADMIN_ROLE else user.branches
    try:
        branches = normalize_branches(raw_branches) if raw_branches else []
    except (TypeError, ValueError):
        raise unauthorized from None
    if not isinstance(claimed_branches, list) or claimed_branches != branches:
        raise unauthorized
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "branches": branches,
    }


def require_admin(user: dict = Depends(authenticate_user)) -> dict:
    if user["role"] != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere el rol de administrador.",
        )
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        requested_role=payload.role,
        requested_branches=[payload.branch],
        role=None,
        branches=None,
        status="pending",
        is_active=False,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese correo.",
        ) from None
    db.refresh(user)
    return {
        "message": "Solicitud registrada. Un administrador debe asignar tus permisos antes de iniciar sesión.",
        "user": user_response(user),
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email))
    try:
        valid_password = user is not None and verify_password(
            payload.password, user.password_hash
        )
    except (ValueError, UnknownHashError):
        valid_password = False
    if not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status != "active" or not user.is_active or user.role not in ALL_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta está pendiente de aprobación o deshabilitada.",
        )
    raw_branches = list(BRANCHES) if user.role == ADMIN_ROLE else user.branches
    try:
        branches = normalize_branches(raw_branches) if raw_branches else []
    except (TypeError, ValueError):
        branches = []
    if not branches:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un administrador debe asignar una sucursal antes del acceso.",
        )

    try:
        token = create_access_token(user.id, user.role, branches)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La autenticación no está configurada.",
        ) from None
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_response(user),
    }


@router.get("/me")
def get_current_user(user: dict = Depends(authenticate_user)) -> dict:
    return user


@router.get("/admin/users")
def list_users(
    _admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return {"users": [user_response(user) for user in users]}


@router.patch("/admin/users/{user_id}")
def update_user_access(
    user_id: int,
    payload: UserAccessUpdate,
    _admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if not payload.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Indica un rol o un estado para actualizar.",
        )

    user = db.get(User, user_id)
    if user is None or user.role == ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el usuario.",
        )
    if "branches" in payload.model_fields_set and payload.branches is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Asigna al menos una sucursal explícitamente.",
        )

    if payload.role is not None:
        user.role = payload.role
        user.requested_role = None
    if payload.branches is not None:
        user.branches = payload.branches
        user.requested_branches = None

    activating = (
        payload.role is not None and payload.is_active is None
    ) or payload.is_active is True
    if activating and not user.branches:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Asigna sucursales explícitamente antes de activar la cuenta.",
        )
    if payload.role is not None and payload.is_active is None:
        user.is_active = True
        user.status = "active"
    if payload.is_active is not None:
        if payload.is_active and user.role is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Asigna un rol operativo antes de activar la cuenta.",
            )
        user.is_active = payload.is_active
        user.status = "active" if payload.is_active else "disabled"

    db.commit()
    db.refresh(user)
    return {"user": user_response(user)}
