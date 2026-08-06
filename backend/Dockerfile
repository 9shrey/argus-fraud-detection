FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project --no-dev

COPY app ./app
RUN uv sync --no-dev

# Trains against synthetic data at image build time — the model ships baked
# into the image rather than being trained at container start, so a cold
# start doesn't pay an 8-second training cost (and stays reproducible: the
# same image always serves the same model version).
RUN uv run python -m app.ml.train

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
