"""Tests for ST-02: Pydantic v2 data models."""
from datetime import datetime, timezone

import pytest

from app.models import (
    CooperativeMessage,
    HazardMessage,
    HazardType,
    InformationSource,
    MessagePriority,
    MessageType,
    Position,
    RiskLevel,
    RiskResult,
    Recommendation,
    ExplanationSource,
    SceneObservation,
    VehicleDirection,
    VehicleManeuver,
    VehicleState,
)


# ── 1. Position can be created with x, y ─────────────────────────────────────

def test_position_creation():
    pos = Position(x=1.5, y=-3.0)
    assert pos.x == 1.5
    assert pos.y == -3.0


# ── 2. VehicleState confidence fields are floats ─────────────────────────────

def test_vehicle_state_fields_are_correct_types():
    vs = VehicleState(
        vehicle_id="CAR_A",
        position=Position(x=100.0, y=50.0),
        road_segment="HIGHWAY_101_N",
        speed_mph=65.0,
        heading_degrees=90.0,
        direction=VehicleDirection.EAST,
        lane=2,
        source=InformationSource.TELEMETRY_DERIVED,
    )
    assert isinstance(vs.speed_mph, float)
    assert isinstance(vs.acceleration, float)
    assert isinstance(vs.heading_degrees, float)


# ── 3. HazardMessage auto-generates hazard_id starting with "HZD_" ───────────

def test_hazard_message_auto_id():
    from app.models.hazard import HazardMessage, HazardType
    msg = HazardMessage(
        hazard_type=HazardType.ROAD_DEBRIS,
        source_vehicle="CAR_B",
        road_segment="HIGHWAY_101_N",
        position=Position(x=230.0, y=45.0),
        confidence=0.85,
        source=InformationSource.VISION_DERIVED,
    )
    assert msg.hazard_id.startswith("HZD_")


# ── 4. CooperativeMessage auto-generates message_id starting with "MSG_" ─────

def test_cooperative_message_auto_id():
    msg = CooperativeMessage(
        source_vehicle="CAR_A",
        message_type=MessageType.HAZARD,
        priority=MessagePriority.HIGH_PRIORITY,
        road_segment="HIGHWAY_101_N",
        position=Position(x=200.0, y=45.0),
    )
    assert msg.message_id.startswith("MSG_")


# ── 5. RiskResult.deterministic is always True by default ────────────────────

def test_risk_result_deterministic_default():
    result = RiskResult(
        risk=RiskLevel.HIGH,
        confidence=0.9,
        assessed_vehicle_id="CAR_A",
    )
    assert result.deterministic is True


# ── 6. InformationSource enum has three expected values ──────────────────────

def test_information_source_enum_values():
    values = {e.value for e in InformationSource}
    assert values == {"VISION_DERIVED", "TELEMETRY_DERIVED", "SYNTHETIC_SCENARIO"}


# ── 7. SceneObservation.prohibited_fields_stripped defaults to empty list ────

def test_scene_observation_prohibited_fields_default():
    obs = SceneObservation(
        source_vehicle="CAR_B",
        scene_summary="Clear road ahead.",
    )
    assert obs.prohibited_fields_stripped == []


# ── 8. HazardType includes HIDDEN_PEDESTRIAN and WRONG_WAY_VEHICLE ───────────

def test_hazard_type_includes_required_values():
    assert HazardType.HIDDEN_PEDESTRIAN.value == "HIDDEN_PEDESTRIAN"
    assert HazardType.WRONG_WAY_VEHICLE.value == "WRONG_WAY_VEHICLE"
