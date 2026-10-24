from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.evidence_store import evidence_store
from app.models import HazardMessage, HazardStatus

router = APIRouter(prefix="/api/hazards", tags=["hazards"])


class _EvidenceBody(BaseModel):
    vehicle_id: str
    confidence: float


@router.get("/")
def list_hazards(
    road_segment: Optional[str] = None,
    status: Optional[HazardStatus] = None,
) -> list[HazardMessage]:
    """Return active (non-expired) hazards, with optional filters."""
    hazards = evidence_store.all_hazards()
    if road_segment is not None:
        hazards = [h for h in hazards if h.road_segment == road_segment]
    if status is not None:
        hazards = [h for h in hazards if h.status == status]
    return hazards


@router.get("/{hazard_id}")
def get_hazard(hazard_id: str) -> HazardMessage:
    """Return a single hazard by ID (404 if not found)."""
    hazard = evidence_store.get_hazard(hazard_id)
    if hazard is None:
        raise HTTPException(status_code=404, detail=f"Hazard '{hazard_id}' not found")
    return hazard


@router.post("/", status_code=201)
def add_hazard(hazard: HazardMessage) -> HazardMessage:
    """Add a new hazard to the store."""
    evidence_store.add_hazard(hazard)
    return hazard


@router.post("/{hazard_id}/confirm")
async def confirm_hazard(hazard_id: str, body: _EvidenceBody) -> HazardMessage:
    """Record a confirmation from another vehicle and broadcast the update."""
    hazard = evidence_store.confirm_hazard(hazard_id, body.vehicle_id, body.confidence)
    if hazard is None:
        raise HTTPException(status_code=404, detail=f"Hazard '{hazard_id}' not found")

    from app.api.ws import ws_manager

    await ws_manager.broadcast({"type": "hazard_update", "payload": hazard.model_dump(mode="json")})
    return hazard


@router.post("/{hazard_id}/conflict")
async def conflict_hazard(hazard_id: str, body: _EvidenceBody) -> HazardMessage:
    """Record a conflicting observation and broadcast the update."""
    hazard = evidence_store.conflict_hazard(hazard_id, body.vehicle_id, body.confidence)
    if hazard is None:
        raise HTTPException(status_code=404, detail=f"Hazard '{hazard_id}' not found")

    from app.api.ws import ws_manager

    await ws_manager.broadcast({"type": "hazard_update", "payload": hazard.model_dump(mode="json")})
    return hazard
