from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core.evidence_store import evidence_store
from app.core.relevance_filter import filter_recipients
from app.models import CooperativeMessage

router = APIRouter(prefix="/api/messages", tags=["messages"])


@router.get("/")
def list_messages(
    limit: int = 50,
    road_segment: Optional[str] = None,
    vehicle_id: Optional[str] = None,
) -> list[CooperativeMessage]:
    """Return recent cooperative messages, with optional filters."""
    messages = evidence_store.recent_messages(limit=limit)
    if road_segment is not None:
        messages = [m for m in messages if m.road_segment == road_segment]
    if vehicle_id is not None:
        messages = [
            m
            for m in messages
            if not m.intended_recipients or vehicle_id in m.intended_recipients
        ]
    return messages


@router.get("/{message_id}")
def get_message(message_id: str) -> CooperativeMessage:
    """Return a single message by ID (404 if not found)."""
    for msg in evidence_store.recent_messages(limit=evidence_store._max_messages):
        if msg.message_id == message_id:
            return msg
    raise HTTPException(status_code=404, detail=f"Message '{message_id}' not found")


@router.post("/", status_code=201)
async def post_message(message: CooperativeMessage) -> CooperativeMessage:
    """Submit a cooperative message, run relevance filter, and broadcast via WebSocket."""
    # Determine recipients if not already set
    if not message.intended_recipients:
        recipients = filter_recipients(
            message,
            evidence_store.all_vehicles(),
            evidence_store.all_zones(),
            message.source_vehicle,
        )
        message.intended_recipients = recipients

    evidence_store.add_message(message)

    # Broadcast via WebSocket (import here to avoid circular imports)
    from app.api.ws import ws_manager

    await ws_manager.broadcast({"type": "message", "payload": message.model_dump(mode="json")})

    return message
