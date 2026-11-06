import os
from datetime import datetime, timedelta, timezone
from typing import Sequence

import jwt
from passlib.context import CryptContext


JWT_ALGORITHM = "HS256"
password_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def get_jwt_settings() -> tuple[str, str, str, int]:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET debe contener al menos 32 bytes.")

    issuer = os.getenv("JWT_ISSUER", "rio-claro-api")
    audience = os.getenv("JWT_AUDIENCE", "rio-claro-frontend")
    try:
        expires_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
    except ValueError:
        raise RuntimeError("JWT_EXPIRE_MINUTES debe ser un entero positivo.") from None
    if not issuer or not audience or expires_minutes < 1:
        raise RuntimeError("La configuración de JWT no es válida.")
    return secret, issuer, audience, expires_minutes


def validate_jwt_configuration() -> None:
    get_jwt_settings()


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(
    user_id: int, role: str, branches: Sequence[str]
) -> str:
    secret, issuer, audience, expires_minutes = get_jwt_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "role": role,
        "branches": list(branches),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "iss": issuer,
        "aud": audience,
    }
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    secret, issuer, audience, _ = get_jwt_settings()
    return jwt.decode(
        token,
        secret,
        algorithms=[JWT_ALGORITHM],
        audience=audience,
        issuer=issuer,
        options={
            "require": [
                "sub",
                "role",
                "branches",
                "iat",
                "exp",
                "iss",
                "aud",
            ]
        },
    )
