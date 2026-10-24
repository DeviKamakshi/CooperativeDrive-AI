from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.evidence_store import evidence_store
from app.core import risk_engine
from app.models import RiskResult

router = APIRouter(prefix="/api/risk", tags=["risk"])


class _RiskRequest(BaseModel):
    vehicle_id: str
    include_explanation: bool = False


@router.post("/assess")
def assess_risk(body: _RiskRequest) -> RiskResult:
    """Deterministic risk assessment for a vehicle.

    When include_explanation is True, appends a natural-language explanation via
    watsonx (with deterministic fallback). The risk/confidence/deterministic fields
    are never modified by this step.
    """
    vehicle = evidence_store.get_vehicle(body.vehicle_id)
    if vehicle is None:
        raise HTTPException(
            status_code=404, detail=f"Vehicle '{body.vehicle_id}' not found"
        )

    hazards = evidence_store.hazards_for_vehicle(vehicle)
    intent_messages = evidence_store.intent_messages()

    risk_result = risk_engine.assess_risk(vehicle, hazards, intent_messages)

    if body.include_explanation:
        from app.watsonx.explainer import explain_risk
        risk_result = explain_risk(risk_result)

    return risk_result
