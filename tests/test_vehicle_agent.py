"""Unit tests for app/core/vehicle_agent.py"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    HazardMessage,
    HazardType,
    InformationSource,
    ManeuverZone,
    MessageType,
    Position,
    VehicleDirection,
    VehicleManeuver,
    VehicleState,
)
from app.core.evidence_store import EvidenceStore
from app.core.vehicle_agent import VehicleAgent
from app.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vehicle(
    vehicle_id: str = "V1",
    acceleration: float = 0.0,
    maneuver: VehicleManeuver = VehicleManeuver.KEEP_LANE,
    x: float = 0.0,
    y: float = 0.0,
) -> VehicleState:
    return VehicleState(
        vehicle_id=vehicle_id,
        position=Position(x=x, y=y),
        road_segment="seg-1",
        speed_mph=30.0,
        acceleration=acceleration,
        heading_degrees=0.0,
        direction=VehicleDirection.NORTH,
        lane=1,
        intended_maneuver=maneuver,
        source=InformationSource.SYNTHETIC_SCENARIO,
    )


def _make_hazard(hazard_type: HazardType = HazardType.ROAD_DEBRIS) -> HazardMessage:
    return HazardMessage(
        hazard_type=hazard_type,
        source_vehicle="V1",
        road_segment="seg-1",
        position=Position(x=0.0, y=0.0),
        confidence=0.9,
        source=InformationSource.SYNTHETIC_SCENARIO,
    )


def _make_zone(x: float = 0.0, y: float = 0.0, radius_m: float = 100.0) -> ManeuverZone:
    return ManeuverZone(
        zone_id="z1",
        zone_type="INTERSECTION",
        road_segment="seg-1",
        center=Position(x=x, y=y),
        radius_m=radius_m,
        active=True,
    )


@pytest.fixture()
def store() -> EvidenceStore:
    s = EvidenceStore()
    return s


@pytest.fixture()
def agent(store: EvidenceStore) -> VehicleAgent:
    return VehicleAgent(vehicle_id="V1", store=store)


# ---------------------------------------------------------------------------
# 1. Sudden braking generates HAZARD message
# ---------------------------------------------------------------------------

def test_sudden_braking_generates_message(agent):
    """Acceleration below braking_threshold_ms2 → SUDDEN_BRAKING HAZARD message."""
    vehicle = _make_vehicle(acceleration=settings.braking_threshold_ms2 - 1.0)  # -5.0
    msgs = agent.evaluate(vehicle, zones=[], new_hazards=[])
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.message_type == MessageType.HAZARD
    assert msg.payload["hazard_type"] == HazardType.SUDDEN_BRAKING.value


# ---------------------------------------------------------------------------
# 2. No SUDDEN_BRAKING when acceleration is above threshold
# ---------------------------------------------------------------------------

def test_no_broadcast_below_braking_threshold(agent):
    """Acceleration -3.0 m/s² (above -4.0 threshold) → no SUDDEN_BRAKING message."""
    vehicle = _make_vehicle(acceleration=-3.0)
    msgs = agent.evaluate(vehicle, zones=[], new_hazards=[])
    braking_msgs = [m for m in msgs if m.payload.get("hazard_type") == HazardType.SUDDEN_BRAKING.value]
    assert braking_msgs == []


# ---------------------------------------------------------------------------
# 3. Maneuver change generates INTENT message
# ---------------------------------------------------------------------------

def test_maneuver_change_generates_intent(agent):
    """Maneuver changes KEEP_LANE → CHANGE_RIGHT → INTENT message generated."""
    prev = _make_vehicle(maneuver=VehicleManeuver.KEEP_LANE)
    curr = _make_vehicle(maneuver=VehicleManeuver.CHANGE_RIGHT)
    msgs = agent.evaluate(curr, zones=[], new_hazards=[], previous_state=prev)
    intent_msgs = [m for m in msgs if m.message_type == MessageType.INTENT]
    assert len(intent_msgs) == 1
    assert intent_msgs[0].payload["intended_maneuver"] == VehicleManeuver.CHANGE_RIGHT.value


# ---------------------------------------------------------------------------
# 4. First tick with KEEP_LANE → no INTENT message
# ---------------------------------------------------------------------------

def test_no_intent_on_keep_lane_start(agent):
    """First tick with KEEP_LANE (no previous state) → no INTENT message."""
    vehicle = _make_vehicle(maneuver=VehicleManeuver.KEEP_LANE)
    msgs = agent.evaluate(vehicle, zones=[], new_hazards=[])
    intent_msgs = [m for m in msgs if m.message_type == MessageType.INTENT]
    assert intent_msgs == []


# ---------------------------------------------------------------------------
# 5. Vehicle in ManeuverZone → TELEMETRY_UPDATE generated
# ---------------------------------------------------------------------------

def test_telemetry_in_zone(agent):
    """Vehicle inside a ManeuverZone → TELEMETRY_UPDATE message generated."""
    vehicle = _make_vehicle(x=0.0, y=0.0, maneuver=VehicleManeuver.KEEP_LANE)
    zone = _make_zone(x=0.0, y=0.0, radius_m=100.0)
    msgs = agent.evaluate(vehicle, zones=[zone], new_hazards=[])
    telemetry_msgs = [m for m in msgs if m.message_type == MessageType.TELEMETRY_UPDATE]
    assert len(telemetry_msgs) == 1


# ---------------------------------------------------------------------------
# 6. Telemetry is rate-limited
# ---------------------------------------------------------------------------

def test_telemetry_rate_limited(agent):
    """Two ticks within rate_limit window → only one TELEMETRY_UPDATE total."""
    vehicle = _make_vehicle(x=0.0, y=0.0, maneuver=VehicleManeuver.KEEP_LANE)
    zone = _make_zone(x=0.0, y=0.0, radius_m=100.0)

    # First tick — should broadcast
    msgs1 = agent.evaluate(vehicle, zones=[zone], new_hazards=[])
    t1 = [m for m in msgs1 if m.message_type == MessageType.TELEMETRY_UPDATE]
    assert len(t1) == 1

    # Second tick immediately (within rate limit) — should NOT broadcast again
    msgs2 = agent.evaluate(vehicle, zones=[zone], new_hazards=[])
    t2 = [m for m in msgs2 if m.message_type == MessageType.TELEMETRY_UPDATE]
    assert len(t2) == 0


# ---------------------------------------------------------------------------
# 7. No TELEMETRY outside zone with KEEP_LANE
# ---------------------------------------------------------------------------

def test_no_telemetry_outside_zone_keep_lane(agent):
    """KEEP_LANE, vehicle far from zone → no TELEMETRY_UPDATE."""
    vehicle = _make_vehicle(x=9999.0, y=9999.0, maneuver=VehicleManeuver.KEEP_LANE)
    zone = _make_zone(x=0.0, y=0.0, radius_m=100.0)
    msgs = agent.evaluate(vehicle, zones=[zone], new_hazards=[])
    telemetry_msgs = [m for m in msgs if m.message_type == MessageType.TELEMETRY_UPDATE]
    assert telemetry_msgs == []


# ---------------------------------------------------------------------------
# 8. New hazard passed in → HAZARD message generated
# ---------------------------------------------------------------------------

def test_new_hazard_generates_hazard_message(agent):
    """A new hazard passed to evaluate → produces one HAZARD message."""
    vehicle = _make_vehicle()
    hazard = _make_hazard(HazardType.ROAD_DEBRIS)
    msgs = agent.evaluate(vehicle, zones=[], new_hazards=[hazard])
    hazard_msgs = [m for m in msgs if m.message_type == MessageType.HAZARD]
    assert len(hazard_msgs) == 1
    assert hazard_msgs[0].hazard_ref == hazard.hazard_id


# ---------------------------------------------------------------------------
# 9. Same hazard is not reported twice
# ---------------------------------------------------------------------------

def test_hazard_not_reported_twice(agent):
    """Same hazard passed in two consecutive ticks → only one HAZARD message total."""
    vehicle = _make_vehicle()
    hazard = _make_hazard(HazardType.ROAD_DEBRIS)

    msgs1 = agent.evaluate(vehicle, zones=[], new_hazards=[hazard])
    msgs2 = agent.evaluate(vehicle, zones=[], new_hazards=[hazard])

    h1 = [m for m in msgs1 if m.message_type == MessageType.HAZARD]
    h2 = [m for m in msgs2 if m.message_type == MessageType.HAZARD]
    assert len(h1) == 1
    assert len(h2) == 0
