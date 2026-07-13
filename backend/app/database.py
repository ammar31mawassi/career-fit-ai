from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import ROOT_DIR, get_settings


def _resolve_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not database_url.startswith("sqlite:///"):
        return database_url
    raw_path = database_url.replace("sqlite:///", "", 1)
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


settings = get_settings()
database_url = _resolve_database_url(settings.database_url)
engine_options: dict[str, object] = {"echo": False, "pool_pre_ping": True}
if database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    # Supabase transaction pooling multiplexes database sessions. Keep one tiny
    # warm application pool per serverless instance so middleware and endpoint
    # work can reuse the same TLS connection instead of reconnecting twice per
    # request. The small cap prevents a serverless scale-out connection storm.
    engine_options["connect_args"] = {"prepare_threshold": None}
    engine_options.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=8,
        pool_recycle=180,
        pool_use_lifo=True,
    )
engine = create_engine(database_url, **engine_options)


if database_url.startswith("sqlite"):
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )


def init_db() -> None:
    if settings.app_env == "production":
        return
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
