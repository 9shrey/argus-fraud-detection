from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.engine import engine
from app.routers import alerts, explain, metrics, stream, transactions

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    engine.ensure_seeded()  # creates synthetic user profiles once, no transactions yet
    yield
    engine.stop()


app = FastAPI(
    title="Argus — Real-Time Fraud Detection Engine",
    description=(
        "Synthetic transaction stream, causal feature engineering, an "
        "XGBoost + Isolation Forest ensemble, and SHAP explainability — "
        "scored live and pushed over WebSocket."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(alerts.router)
app.include_router(metrics.router)
app.include_router(explain.router)
app.include_router(stream.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
