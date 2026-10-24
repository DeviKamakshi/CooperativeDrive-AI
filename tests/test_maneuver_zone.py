"""Unit tests for app/core/maneuver_zone.py"""
import math
import pytest

from app.models import (
    ManeuverZone,
    Position,
    VehicleManeuver,
    VehicleDirection,
    VehicleState,
    InformationSource,
)
from app.core.maneuver_zone import (
    is_in_zone,
    find_active_zones,
    should_share_telemetry,
    vehicle_entered_zone,
    vehicle_exited_zone,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def zone():
    return ManeuverZone(
        zone_id="z1",
        zone_type="INTERSECTION",
        road_segment="seg-1",
        center=Position(x=0.0, y=0.0),
        radius_m=50.0,
        active=True,
    )


def _make_vehicle(x: float, y: float, maneuver: VehicleManeuver = VehicleManeuver.KEEP_LANE) -> VehicleState:
    return VehicleState(
        vehicle_id="v1",
        position=Position(x=x, y=y),
        road_segment="seg-1",
        speed_mph=30.0,
        heading_degrees=0.0,
        direction=VehicleDirection.NORTH,
        lane=1,
        intended_maneuver=maneuver,
        source=InformationSource.SYNTHETIC_SCENARIO,
    )


# ---------------------------------------------------------------------------
# is_in_zone
# ---------------------------------------------------------------------------

def test_in_zone_center(zone):
    """Position == zone.center → inside."""
    assert is_in_zone(Position(x=0.0, y=0.0), zone) is True


def test_in_zone_edge(zone):
    """Position at exactly radius_m from center → inside (boundary inclusive)."""
    assert is_in_zone(Position(x=50.0, y=0.0), zone) is True


def test_outside_zone(zone):
    """Position at radius_m + 1 → outside."""
    assert is_in_zone(Position(x=51.0, y=0.0), zone) is False


# ---------------------------------------------------------------------------
# find_active_zones
# ---------------------------------------------------------------------------

def test_find_active_zones(zone):
    """Position inside one of two zones → returns only that zone."""
    zone2 = ManeuverZone(
        zone_id="z2",
        zone_type="MERGE",
        road_segment="seg-2",
        center=Position(x=200.0, y=200.0),
        radius_m=50.0,
        active=True,
    )
    result = find_active_zones(Position(x=10.0, y=10.0), [zone, zone2])
    assert result == [zone]


def test_find_active_zones_inactive(zone):
    """Zone with active=False is excluded even if position is inside."""
    inactive = ManeuverZone(
        zone_id="z3",
        zone_type="MERGE",
        road_segment="seg-1",
        center=Position(x=0.0, y=0.0),
        radius_m=50.0,
        active=False,
    )
    result = find_active_zones(Position(x=0.0, y=0.0), [inactive])
    assert result == []


# ---------------------------------------------------------------------------
# should_share_telemetry
# ---------------------------------------------------------------------------

def test_should_share_telemetry_in_zone(zone):
    """Vehicle inside a zone → should share."""
    vehicle = _make_vehicle(0.0, 0.0, VehicleManeuver.KEEP_LANE)
    assert should_share_telemetry(vehicle, [zone]) is True


def test_should_share_telemetry_active_maneuver(zone):
    """Vehicle with CHANGE_RIGHT but not in zone → should share."""
    vehicle = _make_vehicle(500.0, 500.0, VehicleManeuver.CHANGE_RIGHT)
    assert should_share_telemetry(vehicle, [zone]) is True


def test_should_share_telemetry_keep_lane_no_zone(zone):
    """KEEP_LANE and not in any zone → no need to share."""
    vehicle = _make_vehicle(500.0, 500.0, VehicleManeuver.KEEP_LANE)
    assert should_share_telemetry(vehicle, [zone]) is False


# ---------------------------------------------------------------------------
# vehicle_entered_zone / vehicle_exited_zone
# ---------------------------------------------------------------------------

def test_vehicle_entered_zone(zone):
    """Was outside, now inside → entered."""
    prev = Position(x=200.0, y=0.0)  # outside
    curr = Position(x=10.0, y=0.0)   # inside
    assert vehicle_entered_zone(prev, curr, zone) is True


def test_vehicle_exited_zone(zone):
    """Was inside, now outside → exited."""
    prev = Position(x=10.0, y=0.0)   # inside
    curr = Position(x=200.0, y=0.0)  # outside
    assert vehicle_exited_zone(prev, curr, zone) is True
