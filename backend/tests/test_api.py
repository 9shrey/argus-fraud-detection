from __future__ import annotations

from datetime import datetime

from app.models import Alert, SyntheticUser, Transaction


def _seed_transaction(
    test_sessionmaker, *, risk_score: float = 82.5, is_flagged: bool = True
) -> str:
    db = test_sessionmaker()
    try:
        user = SyntheticUser(
            id="test-user-1",
            name="Test User",
            home_city="Bengaluru",
            avg_amount=500.0,
            std_amount=100.0,
            usual_categories=["groceries"],
            usual_hours=[9, 10, 11],
            known_devices=["dev-abc123"],
        )
        db.add(user)
        txn = Transaction(
            id="test-txn-1",
            user_id=user.id,
            timestamp=datetime(2026, 3, 1, 10, 0, 0),
            amount=49500.0,
            currency="INR",
            channel="card_present",
            merchant="GoldLeaf Jewels",
            merchant_category="jewellery",
            city="Gurugram",
            country="India",
            device_id="dev-abc123",
            is_new_device=False,
            fraud_scenario="structuring_burst",
            is_fraud_label=True,
            risk_score=risk_score,
            is_flagged=is_flagged,
            model_version="v-test",
            scoring_latency_ms=12.3,
        )
        db.add(txn)
        db.flush()
        if is_flagged:
            db.add(
                Alert(
                    transaction_id=txn.id,
                    user_id=user.id,
                    risk_score=risk_score,
                    top_reasons=[
                        {
                            "feature": "amount",
                            "shap_value": 3.1,
                            "feature_value": 49500.0,
                            "direction": "increases_risk",
                        }
                    ],
                )
            )
        db.commit()
        return txn.id
    finally:
        db.close()


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestTransactions:
    def test_empty_list_before_any_seeding(self, client):
        resp = client.get("/transactions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_seeded_transaction(self, client, test_sessionmaker):
        _seed_transaction(test_sessionmaker)
        resp = client.get("/transactions")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == "test-txn-1"
        assert body[0]["is_flagged"] is True

    def test_flagged_only_filter(self, client, test_sessionmaker):
        _seed_transaction(test_sessionmaker, risk_score=82.5, is_flagged=True)
        resp = client.get("/transactions", params={"flagged_only": True})
        assert len(resp.json()) == 1

        # a second, non-flagged transaction shouldn't show up under the filter
        db = test_sessionmaker()
        db.add(
            Transaction(
                id="test-txn-2",
                user_id="test-user-1",
                timestamp=datetime(2026, 3, 1, 11, 0, 0),
                amount=200.0,
                currency="INR",
                channel="upi",
                merchant="QuickCart Mart",
                merchant_category="groceries",
                city="Bengaluru",
                country="India",
                device_id="dev-abc123",
                is_new_device=False,
                is_fraud_label=False,
                risk_score=8.0,
                is_flagged=False,
            )
        )
        db.commit()
        db.close()
        resp3 = client.get("/transactions", params={"flagged_only": True})
        assert len(resp3.json()) == 1  # still just the flagged one

    def test_get_by_id_404_when_missing(self, client):
        resp = client.get("/transactions/does-not-exist")
        assert resp.status_code == 404

    def test_get_by_id_returns_the_transaction(self, client, test_sessionmaker):
        _seed_transaction(test_sessionmaker)
        resp = client.get("/transactions/test-txn-1")
        assert resp.status_code == 200
        assert resp.json()["merchant"] == "GoldLeaf Jewels"


class TestAlerts:
    def test_alert_carries_denormalized_transaction_fields(self, client, test_sessionmaker):
        _seed_transaction(test_sessionmaker, risk_score=91.0, is_flagged=True)
        resp = client.get("/alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["risk_score"] == 91.0
        assert body[0]["merchant"] == "GoldLeaf Jewels"
        assert body[0]["top_reasons"][0]["feature"] == "amount"


class TestMetrics:
    def test_metrics_endpoint_returns_trained_model_report(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert 0.0 <= body["roc_auc"] <= 1.0
        assert body["confusion_matrix"].keys() == {"tp", "fp", "tn", "fn"}
        assert len(body["feature_importance"]) > 0


class TestExplain:
    def test_404_for_unknown_transaction(self, client):
        resp = client.get("/explain/does-not-exist")
        assert resp.status_code == 404

    def test_explains_a_seeded_transaction(self, client, test_sessionmaker):
        _seed_transaction(test_sessionmaker)
        resp = client.get("/explain/test-txn-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["transaction_id"] == "test-txn-1"
        assert 0.0 <= body["risk_score"] <= 100.0
        assert len(body["reasons"]) > 0
        assert "amount" in body["feature_vector"]


class TestStreamControl:
    def test_status_starts_not_running(self, client):
        resp = client.get("/stream/status")
        assert resp.status_code == 200
        assert resp.json()["running"] is False

    def test_start_then_stop_toggles_running(self, client):
        resp = client.post("/stream/start", json={"rate_tps": 5})
        assert resp.status_code == 200
        assert resp.json()["running"] is True

        resp2 = client.post("/stream/stop")
        assert resp2.status_code == 200
        assert resp2.json()["running"] is False
