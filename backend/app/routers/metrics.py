from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import MetricsOut

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=MetricsOut)
def get_metrics() -> dict:
    """Serves the evaluation report `app.ml.train` wrote at training time —
    computed once offline against the chronological test split, not
    recomputed per request."""
    path = Path(settings.model_artifacts_dir) / "metrics.json"
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="No trained model artifacts found — run `uv run python -m app.ml.train` first.",
        )
    return json.loads(path.read_text())
