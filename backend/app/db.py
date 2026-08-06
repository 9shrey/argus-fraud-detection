"""SQLAlchemy engine/session setup.

Sync engine + sessionmaker, used from FastAPI via a `Depends(get_db)`
generator (SQLAlchemy's sync driver runs fine in FastAPI's threadpool for
this workload — the simulator does a few inserts/second, not thousands).
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they don't exist. No migration framework by design —
    this is a single-service demo, not a long-lived production system with
    schema history to preserve (see career-os for the Alembic version of
    this decision, where it's the right call)."""
    from app import models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)
