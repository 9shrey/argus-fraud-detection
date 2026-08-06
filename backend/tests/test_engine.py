"""Direct, synchronous exercise of SimulationEngine._tick — deliberately
NOT going through the async start/stop loop or WebSocket broadcast, both of
which are timing-dependent and better covered by manual/live verification
than a unit test. This checks the part that actually matters
deterministically: one tick generates valid, scored, persisted rows."""

from __future__ import annotations

from app.engine import SimulationEngine
from app.models import Alert, SyntheticUser, Transaction


def test_tick_persists_scored_transactions(test_sessionmaker, monkeypatch):
    monkeypatch.setattr("app.engine.SessionLocal", test_sessionmaker)

    eng = SimulationEngine()  # a fresh instance — not the app-wide singleton
    eng.ensure_seeded()
    assert len(eng._users) > 0

    db = test_sessionmaker()
    seeded_count = db.query(SyntheticUser).count()
    db.close()
    assert seeded_count > 0

    broadcasts = eng._tick()
    assert len(broadcasts) >= 1
    for payload in broadcasts:
        assert payload["type"] == "transaction"
        assert 0.0 <= payload["risk_score"] <= 100.0

    db = test_sessionmaker()
    assert db.query(Transaction).count() == len(broadcasts)
    flagged_in_db = db.query(Transaction).filter(Transaction.is_flagged.is_(True)).count()
    flagged_alerts = db.query(Alert).count()
    assert flagged_in_db == flagged_alerts
    db.close()

    assert eng.total_generated == len(broadcasts)


def test_repeated_ticks_accumulate(test_sessionmaker, monkeypatch):
    monkeypatch.setattr("app.engine.SessionLocal", test_sessionmaker)

    eng = SimulationEngine()
    eng.ensure_seeded()

    total = 0
    for _ in range(5):
        total += len(eng._tick())

    db = test_sessionmaker()
    assert db.query(Transaction).count() == total
    db.close()
    assert eng.total_generated == total
