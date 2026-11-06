from datetime import datetime
from functools import lru_cache
import os
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, String, URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    requested_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
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


def get_db():
    engine = get_engine(os.fspath(get_database_path()))
    with Session(engine) as session:
        yield session
