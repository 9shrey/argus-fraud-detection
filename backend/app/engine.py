"""Background simulation engine: generates the live transaction stream,
scores each event, persists it, and broadcasts it to connected dashboards.

Runs as an asyncio task on the main event loop; the synchronous DB + model
work for each tick is pushed to a worker thread via `asyncio.to_thread` so a
slow SHAP call never blocks the WebSocket loop. The broadcast itself happens
back on the main loop (`WebSocket.send_text` is bound to the loop it was
accepted on — calling it from a worker thread's own loop raises).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.config import settings
from app.db import SessionLocal
from app.ml.scorer import get_scorer
from app.models import Alert, SyntheticUser, Transaction
from app.simulator.generator import generate_live_tick
from app.simulator.profiles import generate_user_profiles
from app.websocket_manager import manager

logger = logging.getLogger("argus.engine")

HISTORY_LOOKBACK_LIMIT = 300


class SimulationEngine:
    def __init__(self) -> None:
        self.running = False
        self.rate_tps = settings.simulation_rate_tps
        self.total_generated = 0
        self.total_flagged = 0
        self._task: asyncio.Task | None = None
        self._users: list[dict] = []

    def ensure_seeded(self) -> None:
        """Idempotent: seeds synthetic users on first call, reuses them
        (and the in-memory cache) after."""
        if self._users:
            return
        db = SessionLocal()
        try:
            existing = db.query(SyntheticUser).count()
            if existing == 0:
                logger.info("Seeding %d synthetic users...", settings.simulation_num_users)
                profiles = generate_user_profiles(settings.simulation_num_users)
                db.bulk_insert_mappings(SyntheticUser, profiles)
                db.commit()
            rows = db.query(SyntheticUser).all()
            self._users = [
                {
                    "id": u.id,
                    "home_city": u.home_city,
                    "avg_amount": u.avg_amount,
                    "std_amount": u.std_amount,
                    "usual_categories": u.usual_categories,
                    "usual_hours": u.usual_hours,
                    "known_devices": u.known_devices,
                }
                for u in rows
            ]
        finally:
            db.close()

    def status(self) -> dict:
        return {
            "running": self.running,
            "rate_tps": self.rate_tps,
            "total_generated": self.total_generated,
            "total_flagged": self.total_flagged,
        }

    def start(self, rate_tps: float | None = None) -> None:
        if rate_tps:
            self.rate_tps = max(rate_tps, 0.1)
        if self.running:
            return
        self.ensure_seeded()
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Simulation started at %.2f tps", self.rate_tps)

    def stop(self) -> None:
        self.running = False
        logger.info("Simulation stop requested")

    def set_rate(self, rate_tps: float) -> None:
        self.rate_tps = max(rate_tps, 0.1)

    async def _run_loop(self) -> None:
        try:
            while self.running:
                await asyncio.sleep(max(1.0 / self.rate_tps, 0.05))
                try:
                    broadcasts = await asyncio.to_thread(self._tick)
                except Exception:
                    logger.exception("Simulation tick failed")
                    continue
                for payload in broadcasts:
                    await manager.broadcast(payload)
        finally:
            self.running = False

    def _fetch_history(self, db, user_id: str, before_ts: datetime) -> list[dict]:
        rows = (
            db.query(Transaction)
            .filter(Transaction.user_id == user_id, Transaction.timestamp < before_ts)
            .order_by(Transaction.timestamp.desc())
            .limit(HISTORY_LOOKBACK_LIMIT)
            .all()
        )
        rows.reverse()  # compute_features wants ascending order, last() = most recent
        return [
            {
                "amount": r.amount,
                "timestamp": r.timestamp,
                "city": r.city,
                "merchant_category": r.merchant_category,
            }
            for r in rows
        ]

    def _tick(self) -> list[dict]:
        """Runs in a worker thread. Pure sync DB + model work; returns the
        list of payloads to broadcast — no asyncio calls in here."""
        now = datetime.now(UTC).replace(tzinfo=None)  # naive UTC — see app/models.py::_now
        events = generate_live_tick(self._users, now, settings.simulation_fraud_rate)

        db = SessionLocal()
        scorer = get_scorer()
        broadcasts: list[dict] = []
        try:
            for event in events:
                # Flushed inserts earlier in this same burst are visible to
                # this SELECT (same session, same DB transaction) — that's
                # what lets a card-testing burst's later items see the
                # earlier ones as velocity history.
                history = self._fetch_history(db, event["user_id"], event["timestamp"])
                result = scorer.score(event, history)

                txn = Transaction(
                    user_id=event["user_id"],
                    timestamp=event["timestamp"],
                    amount=event["amount"],
                    currency=event["currency"],
                    channel=event["channel"],
                    merchant=event["merchant"],
                    merchant_category=event["merchant_category"],
                    city=event["city"],
                    country=event["country"],
                    device_id=event["device_id"],
                    is_new_device=event["is_new_device"],
                    fraud_scenario=event.get("fraud_scenario"),
                    is_fraud_label=event["is_fraud_label"],
                    risk_score=result["risk_score"],
                    is_flagged=result["is_flagged"],
                    model_version=result["model_version"],
                    scoring_latency_ms=result["latency_ms"],
                )
                db.add(txn)
                db.flush()  # assigns txn.id; also visible to the next event's history query

                self.total_generated += 1
                payload = {
                    "type": "transaction",
                    "id": txn.id,
                    "user_id": txn.user_id,
                    "timestamp": txn.timestamp.isoformat(),
                    "amount": txn.amount,
                    "currency": txn.currency,
                    "channel": txn.channel,
                    "merchant": txn.merchant,
                    "merchant_category": txn.merchant_category,
                    "city": txn.city,
                    "country": txn.country,
                    "risk_score": txn.risk_score,
                    "is_flagged": txn.is_flagged,
                }

                if result["is_flagged"]:
                    self.total_flagged += 1
                    db.add(
                        Alert(
                            transaction_id=txn.id,
                            user_id=txn.user_id,
                            risk_score=result["risk_score"],
                            top_reasons=result["reasons"],
                        )
                    )
                    payload["alert"] = {"top_reasons": result["reasons"]}

                broadcasts.append(payload)

            db.commit()
            return broadcasts
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


engine = SimulationEngine()
