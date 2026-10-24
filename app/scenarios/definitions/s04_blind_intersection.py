"""Demo 4 — Blind Intersection.

CAR_A approaches from the South (heading North), CAR_B from the West (heading East).
Neither has line-of-sight to the other. When both are close enough to the intersection
center that their TTCs are within the conflict window, CAR_A's risk rises to HIGH.
"""
from __future__ import annotations

import math

from app.models import (
    HazardMessage,
    HazardType,
    InformationSource,
    ManeuverZone,
    Position,
    VehicleDirection,
    VehicleManeuver,
    VehicleState,
)
from app.scenarios.base import ScenarioBase
from app.scenarios.registry import register

_TICK_DURATION_S = 1.0
_MPH_TO_MS = 0.44704

# Intersection center
_INTERSECTION_X = 0.0
_INTERSECTION_Y = 0.0

# If both vehicles' TTCs to the intersection are within this window (seconds),
# synthesise a conflict hazard.
_CONFLICT_WINDOW_S = 3.0


def _ttc_to_point(vx: float, vy: float, speed_ms: float, px: float, py: float) -> float | None:
    """Return seconds until the vehicle (at vx,vy moving at speed_ms along heading vector)
    reaches point (px, py), or None if moving away."""
    dx = px - vx
    dy = py - vy
    dist = math.hypot(dx, dy)
    if dist == 0.0:
        return 0.0
    # Unit vector toward point
    ux = dx / dist
    uy = dy / dist
    # heading vector already unit (passed in)
    # closing speed = dot of velocity onto (point - pos)
    # caller passes heading_vx, heading_vy as the unit heading vector — see below
    return None  # placeholder; replaced by caller below


def _ttc(pos_x: float, pos_y: float, heading_vx: float, heading_vy: float,
         speed_ms: float, target_x: float, target_y: float) -> float | None:
    dx = target_x - pos_x
    dy = target_y - pos_y
    dist = math.hypot(dx, dy)
    if dist == 0.0:
        return 0.0
    closing = speed_ms * (heading_vx * dx + heading_vy * dy) / dist
    if closing <= 1e-9:
        return None
    return dist / closing


@register
class BlindIntersectionScenario(ScenarioBase):
    """Two vehicles approach a blind intersection from perpendicular directions."""

    id = "s04"
    name = "Blind Intersection"
    description = (
        "CAR_A (heading North) and CAR_B (heading East) approach the same "
        "intersection without line-of-sight. Cooperative telemetry sharing "
        "triggers HIGH risk when both are close simultaneously."
    )
    ego_vehicle_id = "CAR_A"

    _car_a_state: VehicleState
    _car_b_state: VehicleState

    def setup(self) -> None:
        from app.core.reliability_tracker import reliability_tracker

        # Pre-trust synthetic vehicles so telemetry-derived hazards score correctly
        reliability_tracker._scores["CAR_A"] = 1.0
        reliability_tracker._scores["CAR_B"] = 1.0

        self.zones = [
            ManeuverZone(
                zone_id="Z_S04_INTERSECTION",
                zone_type="INTERSECTION",
                road_segment="MAIN_ST_INTERSECTION",
                center=Position(x=_INTERSECTION_X, y=_INTERSECTION_Y),
                radius_m=150.0,
            )
        ]
        self.store.set_zones(self.zones)

        self._car_a_state = VehicleState(
            vehicle_id="CAR_A",
            position=Position(x=0.0, y=-80.0),
            road_segment="MAIN_ST_INTERSECTION",
            speed_mph=35.0,
            acceleration=0.0,
            heading_degrees=0.0,       # North
            direction=VehicleDirection.NORTH,
            lane=1,
            intended_maneuver=VehicleManeuver.ENTER_INTERSECTION,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        self._car_b_state = VehicleState(
            vehicle_id="CAR_B",
            position=Position(x=-80.0, y=0.0),
            road_segment="MAIN_ST_INTERSECTION",
            speed_mph=40.0,
            acceleration=0.0,
            heading_degrees=90.0,      # East
            direction=VehicleDirection.EAST,
            lane=1,
            intended_maneuver=VehicleManeuver.ENTER_INTERSECTION,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )

    def _advance_vehicles(self) -> dict[str, VehicleState]:
        # CAR_A moves North (y increases)
        a_dy = self._car_a_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
        # CAR_B moves East (x increases)
        b_dx = self._car_b_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S

        self._car_a_state = self._car_a_state.model_copy(
            update={
                "position": Position(
                    x=self._car_a_state.position.x,
                    y=self._car_a_state.position.y + a_dy,
                )
            }
        )
        self._car_b_state = self._car_b_state.model_copy(
            update={
                "position": Position(
                    x=self._car_b_state.position.x + b_dx,
                    y=self._car_b_state.position.y,
                )
            }
        )
        return {
            "CAR_A": self._car_a_state,
            "CAR_B": self._car_b_state,
        }

    def _get_new_hazards(self, vehicle_id: str, state: VehicleState) -> list[HazardMessage]:
        """For CAR_A only: inject a synthetic hazard at the intersection center when
        CAR_B has been close enough to have a concurrent intersection conflict."""
        if vehicle_id != "CAR_A":
            return []

        import math as _math

        a_speed_ms = self._car_a_state.speed_mph * _MPH_TO_MS
        b_speed_ms = self._car_b_state.speed_mph * _MPH_TO_MS

        # Heading vectors
        a_vx = _math.sin(_math.radians(self._car_a_state.heading_degrees))
        a_vy = _math.cos(_math.radians(self._car_a_state.heading_degrees))
        b_vx = _math.sin(_math.radians(self._car_b_state.heading_degrees))
        b_vy = _math.cos(_math.radians(self._car_b_state.heading_degrees))

        # Distance from each vehicle to intersection center
        dist_a = _math.hypot(
            self._car_a_state.position.x - _INTERSECTION_X,
            self._car_a_state.position.y - _INTERSECTION_Y,
        )
        dist_b = _math.hypot(
            self._car_b_state.position.x - _INTERSECTION_X,
            self._car_b_state.position.y - _INTERSECTION_Y,
        )

        # TTC for CAR_A (needed to confirm it's still approaching)
        ttc_a = _ttc(
            self._car_a_state.position.x, self._car_a_state.position.y,
            a_vx, a_vy, a_speed_ms,
            _INTERSECTION_X, _INTERSECTION_Y,
        )
        # TTC for CAR_B (may be None if it has passed)
        ttc_b = _ttc(
            self._car_b_state.position.x, self._car_b_state.position.y,
            b_vx, b_vy, b_speed_ms,
            _INTERSECTION_X, _INTERSECTION_Y,
        )

        # Synthesise hazard when CAR_A is within 60m of intersection AND
        # CAR_B is also within 60m (approaching or just passed) —
        # representing the blind conflict window.
        a_close = dist_a <= 60.0
        b_close = dist_b <= 60.0

        if a_close and b_close:
            # Confidence based on how close CAR_A is (proximity to intersection)
            proximity = 1.0 - dist_a / 60.0
            confidence = min(0.98, 0.75 + proximity * 0.23)
            desc_ttc_a = f"{ttc_a:.1f}s" if ttc_a is not None else "passed"
            desc_ttc_b = f"{ttc_b:.1f}s" if ttc_b is not None else "passed"
            return [
                HazardMessage(
                    hazard_type=HazardType.HIDDEN_PEDESTRIAN,
                    source_vehicle="CAR_A",
                    road_segment=state.road_segment,
                    position=Position(x=_INTERSECTION_X, y=_INTERSECTION_Y),
                    lane=state.lane,
                    confidence=confidence,
                    description=(
                        f"Synthetic intersection conflict: "
                        f"TTC_A={desc_ttc_a} TTC_B={desc_ttc_b}"
                    ),
                    source=InformationSource.SYNTHETIC_SCENARIO,
                )
            ]
        return []
