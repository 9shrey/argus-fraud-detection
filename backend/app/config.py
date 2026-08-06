"""Central settings, read from environment / .env via pydantic-settings.

Kept deliberately simple for a demo project: one settings object, no
per-package config split (contrast with career-os, which has one
`*Settings` class per package — appropriate there because each package
ships independently; overkill for a single-service demo).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Falls back to a local SQLite file so `uvicorn app.main:app` works with
    # zero setup; docker-compose / production point this at Postgres.
    database_url: str = "sqlite:///./argus.db"

    # Risk score (0-100) at/above which a scored transaction becomes an Alert.
    risk_threshold: float = 65.0

    # Simulator pacing — transactions/second when a stream is running.
    simulation_rate_tps: float = 2.0
    simulation_fraud_rate: float = 0.06  # share of synthetic txns that are fraud scenarios
    simulation_num_users: int = 150

    # CORS — the deployed frontend origin(s), comma-separated. "*" for local dev.
    cors_origins: str = "*"

    model_artifacts_dir: str = "app/ml/artifacts"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
