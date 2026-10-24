"""Tests for app/core/relevance_filter.py — 10 tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import (
    CooperativeMessage,
    VehicleState,
    VehicleManeuver,
    VehicleDirection,
    MessageType,
    MessagePriority,
    ManeuverZone,
    InformationSource,
    Position,
)
from app.core.relevance_filter import is_relevant_to_vehicle, filter_recipients


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_vehicle(
    vehicle_id: str = "CAR_A",
    x: float = 0.0,
    y: float = 0.0,
    speed_mph: float = 30.0,
    heading_degrees: float = 0.0,  # North
    lane: int = 1,
    target_lane: int | None = None,
    maneuver: VehicleManeuver = VehicleManeuver.KEEP_LANE,
    road_segment: str = "SEG_1",
) -> VehicleState:
    return VehicleState(
        vehicle_id=vehicle_id,
        position=Position(x=x, y=y),
        road_segment=road_segment,
        speed_mph=speed_mph,
        heading_degrees=heading_degrees,
        direction=VehicleDirection.NORTH,
        lane=lane,
        target_lane=target_lane,
        intended_maneuver=maneuver,
        source=InformationSource.SYNTHETIC_SCENARIO,
    )


def _make_message(
    road_segment: str = "SEG_1",
    x: float = 0.0,
    y: float = 50.0,
    lane: int | None = 1,
    message_type: MessageType = MessageType.HAZARD,
    payload: dict | None = None,
    source_vehicle: str = "CAR_B",
) -> CooperativeMessage:
    return CooperativeMessage(
        source_vehicle=source_vehicle,
        message_type=message_type,
        priority=MessagePriority.NORMAL,
        road_segment=road_segment,
        position=Position(x=x, y=y),
        lane=lane,
        payload=payload or {},
    )


def _make_zone(
    center_x: float = 0.0,
    center_y: float = 50.0,
    radius_m: float = 100.0,
    zone_id: str = "ZONE_1",
) -> ManeuverZone:
    return ManeuverZone(
        zone_id=zone_id,
        zone_type="MERGE",
        road_segment="SEG_1",
        center=Position(x=center_x, y=center_y),
        radius_m=radius_m,
        active=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_different_segment_not_relevant():
    """Different road_segment → False immediately."""
    vehicle = _make_vehicle(road_segment="SEG_1")
    msg = _make_message(road_segment="SEG_2")
    assert is_relevant_to_vehicle(msg, vehicle, []) is False


def test_beyond_distance_not_relevant():
    """Hazard more than max_relevance_distance_m away → False."""
    # Default max is 500 m; put vehicle at 0,0 and hazard at 0,600
    vehicle = _make_vehicle(x=0.0, y=0.0, heading_degrees=0.0)
    msg = _make_message(x=0.0, y=600.0)
    assert is_relevant_to_vehicle(msg, vehicle, []) is False


def test_same_lane_relevant():
    """Candidate lane == message lane → True."""
    vehicle = _make_vehicle(lane=1, x=0.0, y=0.0, heading_degrees=0.0)
    msg = _make_message(x=0.0, y=50.0, lane=1)
    assert is_relevant_to_vehicle(msg, vehicle, []) is True


def test_target_lane_relevant():
    """Candidate target_lane == message lane → True."""
    vehicle = _make_vehicle(lane=1, target_lane=2, x=0.0, y=0.0, heading_degrees=0.0)
    msg = _make_message(x=0.0, y=50.0, lane=2)
    assert is_relevant_to_vehicle(msg, vehicle, []) is True


def test_already_passed_not_relevant():
    """Candidate has already passed the hazard (hazard is behind) → False."""
    # Vehicle at y=200, heading North (0°). Hazard at y=50 (behind it).
    vehicle = _make_vehicle(x=0.0, y=200.0, heading_degrees=0.0, lane=1)
    msg = _make_message(x=0.0, y=50.0, lane=1)
    assert is_relevant_to_vehicle(msg, vehicle, []) is False


def test_wrong_way_directional_filter():
    """WRONG_WAY hazard: candidate heading away from hazard → False."""
    # Vehicle at y=0, heading South (180°). Hazard at y=50 (ahead is South, so y=-50).
    # Hazard is at y=50, which is North of vehicle — candidate is moving away.
    vehicle = _make_vehicle(
        x=0.0, y=0.0,
        heading_degrees=180.0,  # South
        lane=1,
    )
    msg = _make_message(
        x=0.0, y=50.0,  # North of vehicle (behind relative to South heading)
        lane=1,
        payload={"hazard_type": "WRONG_WAY_VEHICLE"},
    )
    # dot product of South heading and North vector is negative → ALREADY_PASSED or DIRECTION_CHECK
    assert is_relevant_to_vehicle(msg, vehicle, []) is False


def test_path_intersection_relevant():
    """Candidate's projected path passes close to hazard → True."""
    # Vehicle at (0,0) heading North (0°) at 30 mph → ~13.4 m/s
    # After look_ahead (8s): y ≈ 107 m
    # Hazard at (2, 50) — 2 m off the straight-north path, well within PATH_WIDTH_M=4
    vehicle = _make_vehicle(x=0.0, y=0.0, heading_degrees=0.0, lane=3, speed_mph=30.0)
    msg = _make_message(x=2.0, y=50.0, lane=1)  # different lane, but in path
    assert is_relevant_to_vehicle(msg, vehicle, []) is True


def test_intent_conflict_same_target_lane():
    """INTENT message: candidate's target_lane == other vehicle's target_lane → True."""
    vehicle = _make_vehicle(lane=1, target_lane=2, x=0.0, y=0.0, heading_degrees=0.0)
    msg = _make_message(
        x=5.0, y=40.0,
        lane=1,  # source is in lane 1
        message_type=MessageType.INTENT,
        payload={"target_lane": 2, "intended_maneuver": "CHANGE_LEFT"},
    )
    assert is_relevant_to_vehicle(msg, vehicle, []) is True


def test_zone_overlap_relevant():
    """Both message position and candidate position in same zone → True."""
    # Vehicle at (0,0), hazard at (10,10), zone centered at (5,5) radius 50 m
    vehicle = _make_vehicle(x=0.0, y=0.0, heading_degrees=0.0, lane=3)
    msg = _make_message(x=10.0, y=10.0, lane=5)  # different lane
    zone = _make_zone(center_x=5.0, center_y=5.0, radius_m=50.0)
    # Vehicle distance from zone center: sqrt(25+25)=~7m < 50m ✓
    # Message distance from zone center: sqrt(25+25)=~7m < 50m ✓
    assert is_relevant_to_vehicle(msg, vehicle, [zone]) is True


def test_source_vehicle_excluded():
    """filter_recipients never includes the source vehicle."""
    msg = _make_message(source_vehicle="CAR_A", x=0.0, y=50.0, lane=1)

    vehicles = {
        "CAR_A": _make_vehicle(vehicle_id="CAR_A", x=0.0, y=0.0, lane=1, heading_degrees=0.0),
        "CAR_B": _make_vehicle(vehicle_id="CAR_B", x=0.0, y=10.0, lane=1, heading_degrees=0.0),
        "CAR_C": _make_vehicle(vehicle_id="CAR_C", x=0.0, y=20.0, lane=1, heading_degrees=0.0),
    }

    recipients = filter_recipients(msg, vehicles, [], source_vehicle_id="CAR_A")
    assert "CAR_A" not in recipients
    # CAR_B and CAR_C should be included (same lane, same segment, ahead of them)
    assert "CAR_B" in recipients
    assert "CAR_C" in recipients
