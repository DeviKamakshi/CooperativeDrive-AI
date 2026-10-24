"""Tests for app/core/risk_engine.py — 10 tests."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.models import (
    VehicleState,
    VehicleManeuver,
    VehicleDirection,
    InformationSource,
    Position,
    HazardMessage,
    HazardType,
    HazardStatus,
    CooperativeMessage,
    MessageType,
    MessagePriority,
    RiskLevel,
    ReasonCode,
    Recommendation,
)
from app.core.risk_engine import assess_risk
from app.config import settings


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
    heading_degrees: float = 0.0,    # North
    lane: int = 1,
    target_lane: int | None = None,
    maneuver: VehicleManeuver = VehicleManeuver.KEEP_LANE,
) -> VehicleState:
    return VehicleState(
        vehicle_id=vehicle_id,
        position=Position(x=x, y=y),
        road_segment="SEG_1",
        speed_mph=speed_mph,
        heading_degrees=heading_degrees,
        direction=VehicleDirection.NORTH,
        lane=lane,
        target_lane=target_lane,
        intended_maneuver=maneuver,
        source=InformationSource.SYNTHETIC_SCENARIO,
    )


def _make_hazard(
    x: float = 0.0,
    y: float = 50.0,  # directly ahead of default vehicle
    hazard_type: HazardType = HazardType.STOPPED_VEHICLE,
    confidence: float = 0.9,
    lane: int = 1,
    source_vehicle: str = "CAR_B",
    status: HazardStatus = HazardStatus.UNCONFIRMED,
    timestamp: datetime | None = None,
    confirmation_count: int = 1,
) -> HazardMessage:
    return HazardMessage(
        hazard_type=hazard_type,
        source_vehicle=source_vehicle,
        road_segment="SEG_1",
        position=Position(x=x, y=y),
        lane=lane,
        confidence=confidence,
        source=InformationSource.SYNTHETIC_SCENARIO,
        status=status,
        timestamp=timestamp or _now(),
        confirmation_count=confirmation_count,
    )


def _make_intent_message(
    source_vehicle: str,
    target_lane: int,
    x: float = 5.0,
    y: float = 50.0,
    speed_mph: float = 30.0,
    heading_degrees: float = 0.0,
) -> CooperativeMessage:
    return CooperativeMessage(
        source_vehicle=source_vehicle,
        message_type=MessageType.INTENT,
        priority=MessagePriority.NORMAL,
        road_segment="SEG_1",
        position=Position(x=x, y=y),
        payload={
            "target_lane": target_lane,
            "intended_maneuver": VehicleManeuver.CHANGE_LEFT.value,
            "speed_mph": speed_mph,
            "heading_degrees": heading_degrees,
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_hazards_returns_low():
    """No hazards and no intent conflicts → LOW risk."""
    vehicle = _make_vehicle()
    result = assess_risk(vehicle, [], [])
    assert result.risk == RiskLevel.LOW
    assert result.deterministic is True


def test_high_severity_hazard_in_lane_returns_high():
    """WRONG_WAY_VEHICLE in same lane, close and fresh → HIGH."""
    vehicle = _make_vehicle(lane=1)
    hazard = _make_hazard(
        y=30.0,  # 30 m ahead — close
        hazard_type=HazardType.WRONG_WAY_VEHICLE,
        confidence=0.95,
        lane=1,
    )
    result = assess_risk(vehicle, [hazard], [])
    assert result.risk == RiskLevel.HIGH
    assert result.deterministic is True


def test_distant_hazard_returns_low():
    """Hazard 600 m away (beyond default 500 m relevance) → LOW."""
    vehicle = _make_vehicle()
    hazard = _make_hazard(
        y=600.0,  # 600 m ahead
        hazard_type=HazardType.WRONG_WAY_VEHICLE,
        confidence=0.95,
        lane=1,
    )
    # Pass explicit max distance to mirror default config
    result = assess_risk(vehicle, [hazard], [], max_relevance_distance_m=500.0)
    assert result.risk == RiskLevel.LOW
    assert result.deterministic is True


def test_expired_hazard_returns_low():
    """Hazard with timestamp 200 s ago (freshness=0) → LOW."""
    vehicle = _make_vehicle()
    old_ts = datetime.now(timezone.utc) - timedelta(seconds=200)
    hazard = _make_hazard(
        y=40.0,
        hazard_type=HazardType.WRONG_WAY_VEHICLE,
        confidence=0.95,
        lane=1,
        timestamp=old_ts,
    )
    result = assess_risk(vehicle, [hazard], [])
    assert result.risk == RiskLevel.LOW
    assert result.deterministic is True


def test_intent_conflict_simultaneous_lane_change():
    """Two vehicles both targeting Lane 2 → HIGH, INTENT_CONFLICT in reason_codes."""
    # Vehicle A heading north, wants to move to lane 2
    vehicle = _make_vehicle(
        vehicle_id="CAR_A",
        x=0.0, y=0.0,
        speed_mph=40.0,
        heading_degrees=0.0,
        lane=1,
        target_lane=2,
        maneuver=VehicleManeuver.CHANGE_LEFT,
    )
    # CAR_B is nearby, also changing to lane 2
    intent_msg = _make_intent_message(
        source_vehicle="CAR_B",
        target_lane=2,
        x=10.0, y=5.0,
        speed_mph=40.0,
        heading_degrees=0.0,
    )
    result = assess_risk(vehicle, [], [intent_msg])
    assert result.risk in (RiskLevel.MEDIUM, RiskLevel.HIGH)
    assert ReasonCode.INTENT_CONFLICT in result.reason_codes
    assert result.deterministic is True


def test_conflicted_status_discounts_score():
    """CONFLICTED hazard produces a lower score than an equivalent CONFIRMED hazard."""
    vehicle = _make_vehicle(lane=1)
    hazard_confirmed = _make_hazard(
        y=40.0, hazard_type=HazardType.WRONG_WAY_VEHICLE,
        confidence=0.9, lane=1,
        status=HazardStatus.CONFIRMED, confirmation_count=2,
    )
    hazard_conflicted = _make_hazard(
        y=40.0, hazard_type=HazardType.WRONG_WAY_VEHICLE,
        confidence=0.9, lane=1,
        status=HazardStatus.CONFLICTED, confirmation_count=1,
    )
    result_confirmed = assess_risk(vehicle, [hazard_confirmed], [])
    result_conflicted = assess_risk(vehicle, [hazard_conflicted], [])
    assert result_confirmed.confidence > result_conflicted.confidence


def test_deterministic_flag_always_true():
    """RiskResult.deterministic is always True regardless of inputs."""
    vehicle = _make_vehicle()
    # Test with no hazards
    r1 = assess_risk(vehicle, [], [])
    assert r1.deterministic is True

    # Test with a HIGH-risk hazard
    hazard = _make_hazard(y=20.0, hazard_type=HazardType.WRONG_WAY_VEHICLE, lane=1)
    r2 = assess_risk(vehicle, [hazard], [])
    assert r2.deterministic is True


def test_watsonx_explanation_not_set_by_engine():
    """Risk engine never sets watsonx_explanation or watsonx_available=True."""
    vehicle = _make_vehicle()
    hazard = _make_hazard(y=30.0, hazard_type=HazardType.ACCIDENT, lane=1)
    result = assess_risk(vehicle, [hazard], [])
    assert result.watsonx_explanation is None
    assert result.watsonx_available is False


def test_hidden_pedestrian_in_path_returns_high():
    """HIDDEN_PEDESTRIAN directly ahead, confirmed by a second vehicle → HIGH."""
    vehicle = _make_vehicle(
        lane=1,
        heading_degrees=0.0,  # North
        speed_mph=30.0,
        maneuver=VehicleManeuver.TURN_RIGHT,
    )
    # Two vehicles have confirmed this hazard, driving up fused_confidence
    hazard = _make_hazard(
        y=20.0,  # 20 m directly ahead
        hazard_type=HazardType.HIDDEN_PEDESTRIAN,
        confidence=0.9,
        lane=1,
        confirmation_count=2,
    )
    result = assess_risk(vehicle, [hazard], [])
    assert result.risk == RiskLevel.HIGH
    assert result.deterministic is True


def test_recommendation_remain_in_lane_on_lane_change_with_hazard():
    """Vehicle doing CHANGE_RIGHT with a TARGET_LANE_HAZARD → REMAIN_IN_CURRENT_LANE."""
    vehicle = _make_vehicle(
        lane=1,
        target_lane=2,
        maneuver=VehicleManeuver.CHANGE_RIGHT,
        heading_degrees=0.0,
        speed_mph=30.0,
    )
    # Hazard in target lane 2, close and fresh → HIGH
    hazard = _make_hazard(
        y=25.0,
        hazard_type=HazardType.WRONG_WAY_VEHICLE,
        confidence=0.95,
        lane=2,  # target lane
    )
    result = assess_risk(vehicle, [hazard], [])
    # Should be HIGH (wrong way, close, in target lane)
    assert result.risk == RiskLevel.HIGH
    assert result.deterministic is True
    # Vehicle is doing a lane change → REMAIN_IN_CURRENT_LANE
    assert result.recommendation == Recommendation.REMAIN_IN_CURRENT_LANE
