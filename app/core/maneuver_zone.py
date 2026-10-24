"""Maneuver zone management utilities."""
from __future__ import annotations

import math

from app.models import ManeuverZone, Position, VehicleManeuver, VehicleState


def is_in_zone(position: Position, zone: ManeuverZone) -> bool:
    """Return True if position is within zone.radius_m of zone.center."""
    dist = math.hypot(position.x - zone.center.x, position.y - zone.center.y)
    return dist <= zone.radius_m


def find_active_zones(position: Position, zones: list[ManeuverZone]) -> list[ManeuverZone]:
    """Return all active zones that contain position."""
    return [z for z in zones if z.active and is_in_zone(position, z)]


def should_share_telemetry(vehicle: VehicleState, zones: list[ManeuverZone]) -> bool:
    """Return True if the vehicle should broadcast a TELEMETRY_UPDATE.

    True when:
      - vehicle is in any active ManeuverZone, OR
      - vehicle.intended_maneuver != VehicleManeuver.KEEP_LANE

    False otherwise (vehicle is cruising, no broadcast needed).
    """
    if vehicle.intended_maneuver != VehicleManeuver.KEEP_LANE:
        return True
    return len(find_active_zones(vehicle.position, zones)) > 0


def vehicle_entered_zone(
    previous_position: Position,
    current_position: Position,
    zone: ManeuverZone,
) -> bool:
    """Return True if the vehicle just entered the zone this tick (was outside, now inside)."""
    return not is_in_zone(previous_position, zone) and is_in_zone(current_position, zone)


def vehicle_exited_zone(
    previous_position: Position,
    current_position: Position,
    zone: ManeuverZone,
) -> bool:
    """Return True if the vehicle just exited the zone this tick (was inside, now outside)."""
    return is_in_zone(previous_position, zone) and not is_in_zone(current_position, zone)
