from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import HISTORY_LOOKBACK_LIMIT
from app.ml.scorer import get_scorer
from app.models import Transaction
from app.schemas import ExplanationOut

router = APIRouter(prefix="/explain", tags=["explain"])


@router.get("/{transaction_id}", response_model=ExplanationOut)
def explain_transaction(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    """Recomputes the full SHAP explanation on demand rather than storing it
    per row at ingest time — a transaction's stored fields are just
    risk_score/is_flagged; the feature vector and reason codes are cheap
    enough (~tens of ms) to regenerate here from the same history the
    original scoring call used."""
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    history_rows = (
        db.query(Transaction)
        .filter(Transaction.user_id == txn.user_id, Transaction.timestamp < txn.timestamp)
        .order_by(Transaction.timestamp.desc())
        .limit(HISTORY_LOOKBACK_LIMIT)
        .all()
    )
    history_rows.reverse()
    history = [
        {
            "amount": r.amount,
            "timestamp": r.timestamp,
            "city": r.city,
            "merchant_category": r.merchant_category,
        }
        for r in history_rows
    ]

    event = {
        "amount": txn.amount,
        "timestamp": txn.timestamp,
        "city": txn.city,
        "merchant_category": txn.merchant_category,
        "channel": txn.channel,
        "is_new_device": txn.is_new_device,
    }

    result = get_scorer().score(event, history)
    return {
        "transaction_id": txn.id,
        "risk_score": result["risk_score"],
        "is_flagged": result["is_flagged"],
        "xgb_probability": result["xgb_probability"],
        "isolation_forest_score": result["isolation_forest_score"],
        "base_value": result["base_value"],
        "reasons": result["reasons"],
        "feature_vector": result["feature_vector"],
    }
