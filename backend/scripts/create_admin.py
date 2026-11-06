"""Crea de forma interactiva la cuenta inicial de administración."""

import getpass
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

try:
    from dotenv import load_dotenv
    from sqlalchemy import select
    from sqlalchemy.orm import Session
except ModuleNotFoundError as error:
    if error.name not in {"dotenv", "sqlalchemy"}:
        raise
    requirements = REPOSITORY_ROOT / "backend" / "requirements.txt"
    print(
        f"Falta la dependencia Python '{error.name}'. Instálala con el mismo "
        f"intérprete que ejecuta este script:\n"
        f'  "{sys.executable}" -m pip install -r "{requirements}"',
        file=sys.stderr,
    )
    raise SystemExit(1) from None

load_dotenv(REPOSITORY_ROOT / ".env")

from backend.app.database import User, get_database_path, get_engine, initialize_database
from backend.app.security import hash_password


def main() -> int:
    initialize_database()
    email = input("Correo del administrador: ").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        print("Ingresa un correo electrónico válido.", file=sys.stderr)
        return 1

    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirma la contraseña: ")
    if not 12 <= len(password) <= 128:
        print(
            "La contraseña debe tener entre 12 y 128 caracteres.",
            file=sys.stderr,
        )
        return 1
    if password != confirmation:
        print("Las contraseñas no coinciden.", file=sys.stderr)
        return 1

    engine = get_engine(str(get_database_path()))
    with Session(engine) as session:
        if session.scalar(select(User).where(User.email == email)):
            print("Ya existe una cuenta con ese correo.", file=sys.stderr)
            return 1
        session.add(
            User(
                email=email,
                password_hash=hash_password(password),
                requested_role=None,
                role="admin",
                status="active",
                is_active=True,
            )
        )
        session.commit()

    print("Cuenta de administración creada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
