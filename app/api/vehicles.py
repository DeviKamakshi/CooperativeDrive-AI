from fastapi import APIRouter, HTTPException

from app.core.evidence_store import evidence_store
from app.models import VehicleState

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


@router.get("/")
def list_vehicles() -> list[VehicleState]:
    """Return all registered vehicle states."""
    return list(evidence_store.all_vehicles().values())


@router.get("/{vehicle_id}")
def get_vehicle(vehicle_id: str) -> VehicleState:
    """Return state for a single vehicle (404 if not found)."""
    vehicle = evidence_store.get_vehicle(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Vehicle '{vehicle_id}' not found")
    return vehicle


@router.post("/{vehicle_id}/state", status_code=201)
def upsert_vehicle_state(vehicle_id: str, state: VehicleState) -> VehicleState:
    """Upsert a vehicle state. vehicle_id in path must match body."""
    state.vehicle_id = vehicle_id
    evidence_store.update_vehicle(state)
    return state


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: str) -> None:
    """Remove a vehicle from the store."""
    evidence_store.remove_vehicle(vehicle_id)
