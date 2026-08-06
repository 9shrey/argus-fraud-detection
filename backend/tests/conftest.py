from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.engine import engine as simulation_engine
from app.main import app


@pytest.fixture()
def test_sessionmaker(tmp_path):
    """A fresh SQLite file per test — isolated from the real dev DB
    (`argus.db`) and from every other test."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


@pytest.fixture()
def client(test_sessionmaker, monkeypatch) -> Iterator[TestClient]:
    """A TestClient wired to the isolated test DB — both via FastAPI's own
    `get_db` dependency (regular routes) and by patching the simulation
    engine's module-level `SessionLocal` (its background task doesn't go
    through `Depends`). Also resets the engine singleton's in-memory state,
    since it otherwise persists across tests in the same pytest session."""

    def override_get_db():
        db = test_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.engine.SessionLocal", test_sessionmaker)
    simulation_engine.running = False
    simulation_engine._users = []
    simulation_engine.total_generated = 0
    simulation_engine.total_flagged = 0

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
