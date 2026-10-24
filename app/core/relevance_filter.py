"""Relevance filter — determines which vehicles should receive a cooperative message."""
from __future__ import annotations

import math

from app.models import CooperativeMessage, VehicleState, MessageType, ManeuverZone
from app.core.ttc import euclidean_distance, heading_to_vector, mph_to_ms
from app.config import settings

_PATH_WIDTH_M = 4.0

# Hazard types whose direction check applies (sourced from message payload)
_DIRECTIONAL_TYPES = {"WRONG_WAY_VEHICLE", "SUDDEN_BRAKING"}


def is_relevant_to_vehicle(
    message: CooperativeMessage,
    candidate: VehicleState,
    all_zones: list[ManeuverZone],
) -> bool:
    """Return True if candidate vehicle should receive this message.

    Steps (evaluated in order):
      1. SAME_SEGMENT  — must match; hard exit on failure
      2. DISTANCE_CHECK — must be within max_relevance_distance_m; hard exit
      3. ALREADY_PASSED — skip if candidate has passed hazard; hard exit
      4. DIRECTION_CHECK — applies only to WRONG_WAY / SUDDEN_BRAKING
      5-8. Soft checks — any True → relevant
    """
    # ------------------------------------------------------------------
    # 1. SAME_SEGMENT — hard gate
    # ------------------------------------------------------------------
    if message.road_segment != candidate.road_segment:
        return False

    # ------------------------------------------------------------------
    # 2. DISTANCE_CHECK
    # ------------------------------------------------------------------
    dist = euclidean_distance(
        message.position.x, message.position.y,
        candidate.position.x, candidate.position.y,
    )
    if dist > settings.max_relevance_distance_m:
        return False

    # ------------------------------------------------------------------
    # 3. ALREADY_PASSED
    # Dot product of candidate velocity vector and vector-to-hazard < 0
    # means the hazard is behind the candidate (in its direction of travel).
    # ------------------------------------------------------------------
    vx, vy = heading_to_vector(candidate.heading_degrees)
    haz_dx = message.position.x - candidate.position.x
    haz_dy = message.position.y - candidate.position.y
    dot = vx * haz_dx + vy * haz_dy
    if dot < 0:
        return False

    # ------------------------------------------------------------------
    # 4. DIRECTION_CHECK (WRONG_WAY and SUDDEN_BRAKING only)
    # Candidate must be travelling *toward* the hazard (positive closing component).
    # ------------------------------------------------------------------
    hazard_type = message.payload.get("hazard_type", "")
    if hazard_type in _DIRECTIONAL_TYPES:
        # Closing component: already computed as dot above.
        # dot > 0 means candidate is heading toward hazard — keep.
        # dot == 0 means perpendicular — not relevant for these types.
        if dot <= 0:
            return False

    # ------------------------------------------------------------------
    # 5–8. Soft relevance checks — any True → return True
    # ------------------------------------------------------------------

    # 5. LANE_RELEVANCE
    msg_lane = message.lane
    if msg_lane is not None:
        if candidate.lane == msg_lane:
            return True
        if candidate.target_lane is not None and candidate.target_lane == msg_lane:
            return True
        # Maneuver will enter message lane (e.g. target_lane set via payload)
        intended_target = message.payload.get("lane")
        if intended_target is not None and candidate.target_lane == intended_target:
            return True

    # 6. PATH_INTERSECTION
    # Project candidate forward by look_ahead_seconds at current speed.
    speed_ms = mph_to_ms(candidate.speed_mph)
    look_ahead_m = speed_ms * settings.look_ahead_seconds
    projected_x = candidate.position.x + vx * look_ahead_m
    projected_y = candidate.position.y + vy * look_ahead_m

    # Closest point on candidate's path segment to the hazard position
    path_dist = _point_to_segment_distance(
        message.position.x, message.position.y,
        candidate.position.x, candidate.position.y,
        projected_x, projected_y,
    )
    if path_dist <= _PATH_WIDTH_M:
        return True

    # 7. MANEUVER_CONFLICT (INTENT messages only)
    if message.message_type == MessageType.INTENT:
        other_target = message.payload.get("target_lane")
        if (
            other_target is not None
            and candidate.target_lane is not None
            and candidate.target_lane == other_target
        ):
            return True

    # 8. ZONE_OVERLAP
    for zone in all_zones:
        if not zone.active:
            continue
        # Check if message position is in this zone
        msg_in_zone = (
            euclidean_distance(
                message.position.x, message.position.y,
                zone.center.x, zone.center.y,
            ) <= zone.radius_m
        )
        # Check if candidate is in this zone
        cand_in_zone = (
            euclidean_distance(
                candidate.position.x, candidate.position.y,
                zone.center.x, zone.center.y,
            ) <= zone.radius_m
        )
        if msg_in_zone and cand_in_zone:
            return True

    return False


def filter_recipients(
    message: CooperativeMessage,
    all_vehicles: dict[str, VehicleState],
    all_zones: list[ManeuverZone],
    source_vehicle_id: str,
) -> list[str]:
    """Return list of vehicle IDs that should receive the message.

    Excludes the source vehicle itself.
    """
    recipients: list[str] = []
    for vid, vehicle in all_vehicles.items():
        if vid == source_vehicle_id:
            continue
        if is_relevant_to_vehicle(message, vehicle, all_zones):
            recipients.append(vid)
    return recipients


# ---------------------------------------------------------------------------
# Internal geometry
# ---------------------------------------------------------------------------


def _point_to_segment_distance(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """Minimum distance from point P to line segment A→B."""
    dx = bx - ax
    dy = by - ay
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0.0:
        # Degenerate segment: A == B
        return math.hypot(px - ax, py - ay)

    # Project P onto AB, clamp t to [0, 1]
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))

    closest_x = ax + t * dx
    closest_y = ay + t * dy
    return math.hypot(px - closest_x, py - closest_y)
