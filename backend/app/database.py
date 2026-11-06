from datetime import datetime
from functools import lru_cache
import json
import os
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    URL,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator

from backend.app.branches import expand_legacy_branches, normalize_branches


class Base(DeclarativeBase):
    pass


class BranchList(TypeDecorator):
    """Persist branch assignments as JSON text and expose Python lists."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        if value is None:
            return None
        return json.dumps(normalize_branches(value), separators=(",", ":"))

    def process_result_value(self, value, _dialect):
        if value is None:
            return None
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, list):
            return None
        return parsed


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    requested_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requested_branches: Mapped[list[str] | None] = mapped_column(
        BranchList(), nullable=True
    )
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    branches: Mapped[list[str] | None] = mapped_column(BranchList(), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InvoiceUpload(Base):
    __tablename__ = "invoice_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    branch: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    uploaded_by: Mapped[int] = mapped_column(Integer, index=True)
    generated_filename: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    vendor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    invoice_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    vendor_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_reasons: Mapped[str] = mapped_column(Text, default="[]")
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    blob_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_nombre: Mapped[str] = mapped_column(String(120))
    cliente_email: Mapped[str] = mapped_column(String(254), index=True)
    sucursal: Mapped[str] = mapped_column(String(32), index=True)
    mensaje: Mapped[str] = mapped_column(Text)
    categoria: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resumen_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    punto_critico: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_analisis: Mapped[str] = mapped_column(String(16), default="pending")
    estado: Mapped[str] = mapped_column(
        String(24), default="received", index=True
    )
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def get_database_path() -> Path:
    configured_path = os.getenv("AUTH_DATABASE_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "users.db"


@lru_cache(maxsize=4)
def get_engine(database_path: str):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        URL.create("sqlite", database=os.fspath(path)),
        connect_args={"check_same_thread": False},
    )


def initialize_database() -> None:
    engine = get_engine(os.fspath(get_database_path()))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        columns = {
            column["name"]
            for column in inspect(connection).get_columns(User.__tablename__)
        }
        if "branches" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN branches TEXT"))
            columns.add("branches")
        if "requested_branches" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN requested_branches TEXT")
            )
            columns.add("requested_branches")
        if "username" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN username VARCHAR(32)")
            )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username "
                "ON users (username COLLATE NOCASE)"
            )
        )

        invoice_columns = {
            column["name"]
            for column in inspect(connection).get_columns(
                InvoiceUpload.__tablename__
            )
        }
        if "generated_filename" not in invoice_columns:
            connection.execute(
                text(
                    "ALTER TABLE invoice_uploads "
                    "ADD COLUMN generated_filename VARCHAR(255)"
                )
            )
        if "reviewed_by" not in invoice_columns:
            connection.execute(
                text("ALTER TABLE invoice_uploads ADD COLUMN reviewed_by INTEGER")
            )
        if "reviewed_at" not in invoice_columns:
            connection.execute(
                text(
                    "ALTER TABLE invoice_uploads "
                    "ADD COLUMN reviewed_at DATETIME"
                )
            )

        legacy_branch = "branch" if "branch" in columns else None
        legacy_requested_branch = (
            "requested_branch" if "requested_branch" in columns else None
        )
        if legacy_branch or legacy_requested_branch:
            selected = ["id", "branches", "requested_branches"]
            if legacy_branch:
                selected.append(legacy_branch)
            if legacy_requested_branch:
                selected.append(legacy_requested_branch)
            rows = connection.execute(
                text(f"SELECT {', '.join(selected)} FROM users")
            ).mappings()
            for row in rows:
                updates = {}
                if row["branches"] is None and legacy_branch:
                    updates["branches"] = expand_legacy_branches(row[legacy_branch])
                if row["requested_branches"] is None and legacy_requested_branch:
                    updates["requested_branches"] = expand_legacy_branches(
                        row[legacy_requested_branch]
                    )
                if updates:
                    assignments = []
                    parameters = {"user_id": row["id"]}
                    for column, value in updates.items():
                        assignments.append(f"{column} = :{column}")
                        parameters[column] = (
                            json.dumps(value, separators=(",", ":"))
                            if value is not None
                            else None
                        )
                    connection.execute(
                        text(
                            f"UPDATE users SET {', '.join(assignments)} "
                            "WHERE id = :user_id"
                        ),
                        parameters,
                    )


def get_db():
    engine = get_engine(os.fspath(get_database_path()))
    with Session(engine) as session:
        yield session
