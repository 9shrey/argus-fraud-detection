from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Denormalized on purpose: the dashboard's alert feed wants amount/
    merchant/city alongside the risk score without a second round trip per
    row, so this joins Transaction rather than returning bare AlertOut."""
    rows = (
        db.query(Alert)
        .options(joinedload(Alert.transaction))
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "transaction_id": a.transaction_id,
            "user_id": a.user_id,
            "risk_score": a.risk_score,
            "top_reasons": a.top_reasons,
            "created_at": a.created_at,
            "amount": a.transaction.amount if a.transaction else None,
            "currency": a.transaction.currency if a.transaction else None,
            "merchant": a.transaction.merchant if a.transaction else None,
            "merchant_category": a.transaction.merchant_category if a.transaction else None,
            "city": a.transaction.city if a.transaction else None,
            "channel": a.transaction.channel if a.transaction else None,
        }
        for a in rows
    ]
