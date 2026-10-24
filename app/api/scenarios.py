"""Scenario API — list, start, tick, stop, and query scenario frames."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from app.scenarios.base import ScenarioBase, ScenarioFrame
from app.scenarios.registry import get_scenario, list_scenarios
from app.api.ws import ws_manager
from app.models import RiskResult
from app.watsonx.explainer import explain_risk

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

# In-memory active scenario and latest frame
_active_scenario: Optional[ScenarioBase] = None
_latest_frame: Optional[ScenarioFrame] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
def list_all_scenarios() -> list[dict]:
    """List metadata for all registered scenarios."""
    return list_scenarios()


@router.post("/{scenario_id}/start", status_code=200)
def start_scenario(scenario_id: str) -> dict[str, Any]:
    """Instantiate, reset, and set up a scenario as the active one."""
    global _active_scenario, _latest_frame

    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    scenario.reset()
    scenario.setup()
    _active_scenario = scenario
    _latest_frame = None
    return {"started": scenario_id, "name": scenario.name}


@router.post("/{scenario_id}/tick")
async def tick_scenario(scenario_id: str) -> dict[str, Any]:
    """Advance the active scenario one tick and return the resulting ScenarioFrame."""
    global _latest_frame

    if _active_scenario is None:
        raise HTTPException(status_code=400, detail="No scenario is currently running")
    if _active_scenario.id != scenario_id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Active scenario is '{_active_scenario.id}', "
                f"not '{scenario_id}'"
            ),
        )

    frame = _active_scenario.tick()

    # Enrich risk result with watsonx / deterministic explanation
    if frame.risk_result:
        risk_obj = RiskResult(**frame.risk_result)
        risk_obj = explain_risk(risk_obj)
        frame.risk_result = risk_obj.model_dump(mode="json")

    _latest_frame = frame
    frame_dict = frame.model_dump()

    # Broadcast to WebSocket clients (fire-and-forget)
    await ws_manager.broadcast({"type": "scenario_frame", "payload": frame_dict})

    return frame_dict


@router.post("/stop", status_code=200)
def stop_scenario() -> dict[str, str]:
    """Stop the active scenario."""
    global _active_scenario, _latest_frame

    _active_scenario = None
    _latest_frame = None
    return {"status": "stopped"}


@router.get("/state")
def scenario_state() -> dict[str, Any]:
    """Return the latest tick frame, or a status dict if nothing is running."""
    if _latest_frame is None:
        return {"status": "no scenario running"}
    return _latest_frame.model_dump()
