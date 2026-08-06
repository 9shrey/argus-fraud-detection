from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.engine import engine
from app.schemas import StreamControl, StreamStatus
from app.websocket_manager import manager

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/status", response_model=StreamStatus)
async def get_status() -> dict:
    return engine.status()


@router.post("/start", response_model=StreamStatus)
async def start_stream(control: StreamControl | None = None) -> dict:
    # Must be `async def`: FastAPI runs sync `def` handlers in a worker
    # threadpool, which has no running event loop — and `engine.start()`
    # calls `asyncio.create_task`, which requires one. Async handlers run
    # directly on the main loop.
    engine.start(rate_tps=control.rate_tps if control else None)
    return engine.status()


@router.post("/stop", response_model=StreamStatus)
async def stop_stream() -> dict:
    engine.stop()
    return engine.status()


@router.post("/rate", response_model=StreamStatus)
async def set_rate(control: StreamControl) -> dict:
    if control.rate_tps:
        engine.set_rate(control.rate_tps)
    return engine.status()


@router.websocket("/ws")
async def stream_ws(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        while True:
            # The client never needs to send anything; this just blocks
            # until disconnect so we notice and clean up the connection set.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
