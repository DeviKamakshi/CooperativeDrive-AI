"""Automated validation tests for all 20 CooperativeDrive AI benchmark scenarios."""
import pytest
from fastapi.testclient import TestClient

from main import app
from scenarios import BENCHMARK_SCENARIOS

client = TestClient(app)


def test_scenarios_endpoint():
    """Validates that GET /api/scenarios returns all 20 benchmark scenarios."""
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) == 20


@pytest.mark.parametrize("scenario", BENCHMARK_SCENARIOS, ids=lambda s: s["name"])
def test_each_benchmark_scenario(scenario):
    """Executes each of the 20 benchmark scenarios against /api/assess and validates expected risk."""
    payload = {
        "vehicle_id": scenario["vehicle_context"]["vehicle_id"],
        "speed": scenario["vehicle_context"]["speed"],
        "current_lane": scenario["vehicle_context"]["current_lane"],
        "target_lane": scenario["vehicle_context"]["target_lane"],
        "direction": scenario["vehicle_context"]["direction"],
        "intended_maneuver": scenario["vehicle_context"]["intended_maneuver"],
        "source_vehicle": scenario["vehicle_context"]["source_vehicle"],
        "observation": scenario["observation"],
    }

    response = client.post("/api/assess", json=payload)
    assert response.status_code == 200
    res = response.json()

    expected_risk = scenario["expected_risk"]
    assert res["risk"] == expected_risk, (
        f"Scenario {scenario['id']} ({scenario['name']}) expected risk {expected_risk}, got {res['risk']}"
    )

    # Specific Scenario Validation Checks:
    if scenario["id"] == 5:
        # Scenario 5: Safe highway merge must be LOW
        assert res["risk"] == "LOW"
    elif scenario["id"] == 13:
        # Scenario 13: Conflicting reports must be MEDIUM
        assert res["risk"] == "MEDIUM"
    elif scenario["id"] == 14:
        # Scenario 14: Multiple vehicles confirm must have HIGH confidence
        assert res["risk"] == "HIGH"
        assert res["confidence"] == "HIGH"
    elif scenario["id"] in (15, 16):
        # Scenario 15 & 16: Irrelevant or non-conflicting hazard -> no warning to CAR_A
        assert res["risk"] == "LOW"
        assert res["recipients"] == [] or "NONE" in res["recipients"]
    elif scenario["id"] == 20:
        # Scenario 20: Completely safe road must be LOW
        assert res["risk"] == "LOW"
