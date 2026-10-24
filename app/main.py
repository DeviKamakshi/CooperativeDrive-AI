import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import hazards, messages, risk, scenarios, vehicles, ws
from app.api.ws import ws_manager
from app.core.evidence_store import evidence_store
from app.core.relevance_filter import filter_recipients
from app.models import (
    CooperativeMessage,
    MessagePriority,
    MessageType,
    Position,
)

logger = logging.getLogger(__name__)

STATIC_DIR = "app/static"


async def _expiry_loop() -> None:
    """Background task: expire hazards every second and broadcast HAZARD_CLEARED."""
    while True:
        await asyncio.sleep(1.0)
        expired_ids = evidence_store.expire_hazards()
        for hid in expired_ids:
            # Build a minimal HAZARD_CLEARED cooperative message
            cleared_msg = CooperativeMessage(
                source_vehicle="SYSTEM",
                message_type=MessageType.HAZARD_CLEARED,
                priority=MessagePriority.NORMAL,
                road_segment="",
                position=Position(x=0.0, y=0.0),
                hazard_ref=hid,
                payload={"hazard_id": hid, "reason": "expired"},
                timestamp=datetime.now(timezone.utc),
            )
            recipients = filter_recipients(
                cleared_msg,
                evidence_store.all_vehicles(),
                evidence_store.all_zones(),
                "SYSTEM",
            )
            cleared_msg.intended_recipients = recipients
            evidence_store.add_message(cleared_msg)
            await ws_manager.broadcast(
                {
                    "type": "hazard_cleared",
                    "payload": cleared_msg.model_dump(mode="json"),
                }
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CooperativeDrive AI starting")
    task = asyncio.create_task(_expiry_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("CooperativeDrive AI shutdown")


app = FastAPI(
    title="CooperativeDrive AI",
    description=(
        "Real-time cooperative driving assistant powered by watsonx.ai. "
        "Vehicles share telemetry and scene observations to detect hazards "
        "and prevent collisions."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(vehicles.router)
app.include_router(messages.router)
app.include_router(hazards.router)
app.include_router(risk.router)
app.include_router(scenarios.router)
app.include_router(ws.router)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(f"{STATIC_DIR}/index.html")


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "CooperativeDrive AI"}
