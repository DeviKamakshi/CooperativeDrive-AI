"""Demo 2 — Highway Merge Conflict.

CAR_HIGHWAY travels East at 65 mph in lane 1. CAR_MERGE approaches from the
on-ramp at 45 mph on a diagonal heading toward merge point (100, 0). The
risk engine detects INSUFFICIENT_MERGE_GAP when their TTCs to the conflict
point are within 3 seconds of each other → HIGH risk.

After tick 8 CAR_HIGHWAY decelerates to create a safe gap → risk drops.
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
# HazardType.ROAD_BLOCKAGE is used — imported via HazardType above
from app.scenarios.base import ScenarioBase
from app.scenarios.registry import register

_TICK_DURATION_S = 1.0
_MPH_TO_MS = 0.44704
_MS_TO_MPH = 2.23694

# Merge conflict point where CAR_MERGE's path crosses lane 1
_MERGE_POINT_X = 100.0
_MERGE_POINT_Y = 0.0

# TTC gap thresholds (seconds)
_CLOSE_GAP = 3.0
_VERY_CLOSE_GAP = 1.5


def _ttc_to_point(pos_x: float, pos_y: float, speed_ms: float,
                  heading_deg: float, px: float, py: float) -> float | None:
    """Return seconds until vehicle reaches (px, py). None if moving away."""
    rad = math.radians(heading_deg)
    vx = math.sin(rad)  # East component
    vy = math.cos(rad)  # North component

    dx = px - pos_x
    dy = py - pos_y
    dist = math.hypot(dx, dy)
    if dist == 0.0:
        return 0.0

    closing = speed_ms * (vx * dx + vy * dy) / dist
    if closing <= 1e-9:
        return None
    return dist / closing


@register
class HighwayMergeScenario(ScenarioBase):
    """TTC-based merge conflict detection — HIGH risk on tight gap, drops after decel."""

    id = "s02"
    name = "Highway Merge"
    description = (
        "CAR_MERGE approaches from on-ramp with tight TTC overlap to conflict "
        "point → HIGH (INSUFFICIENT_MERGE_GAP). After CAR_HIGHWAY decelerates "
        "at tick 8 a safe gap opens → risk drops to MEDIUM or LOW."
    )
    ego_vehicle_id = "CAR_HIGHWAY"

    _car_highway_state: VehicleState
    _car_merge_state: VehicleState

    def setup(self) -> None:
        from app.core.reliability_tracker import reliability_tracker

        reliability_tracker._scores["CAR_HIGHWAY"] = 1.0
        reliability_tracker._scores["CAR_MERGE"] = 1.0

        self.road_images = ["app/static/assets/images/s02/frame_001.jpg"]

        self.zones = [
            ManeuverZone(
                zone_id="Z_S02_MERGE",
                zone_type="MERGE",
                road_segment="HIGHWAY_101_E",
                center=Position(x=50.0, y=-4.0),
                radius_m=200.0,
            )
        ]
        self.store.set_zones(self.zones)

        # CAR_HIGHWAY: travelling East in lane 1 (y=0)
        self._car_highway_state = VehicleState(
            vehicle_id="CAR_HIGHWAY",
            position=Position(x=0.0, y=0.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=65.0,
            acceleration=0.0,
            heading_degrees=90.0,           # East
            direction=VehicleDirection.EAST,
            lane=1,
            target_lane=None,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        # CAR_MERGE: on the on-ramp (lane 0, y=-4), heading toward merge point (100, 0).
        # TTC_highway ≈ 3.44s, TTC_merge ≈ 4.85s → gap ≈ 1.41s < 1.5s → HIGH confidence.
        _dx = _MERGE_POINT_X - (-30.0)
        _dy = _MERGE_POINT_Y - (-4.0)
        _merge_heading = math.degrees(math.atan2(_dx, _dy))  # atan2(East, North)

        self._car_merge_state = VehicleState(
            vehicle_id="CAR_MERGE",
            position=Position(x=-30.0, y=-4.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=60.0,
            acceleration=0.0,
            heading_degrees=_merge_heading,
            direction=VehicleDirection.EAST,
            lane=0,
            target_lane=1,
            intended_maneuver=VehicleManeuver.MERGE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )

    def _advance_vehicles(self) -> dict[str, VehicleState]:
        # After tick 8: CAR_HIGHWAY decelerates to create safe gap
        if self.tick_index == 8:
            self._car_highway_state = self._car_highway_state.model_copy(
                update={"acceleration": -2.0}
            )

        # Update speeds based on acceleration
        def _update_speed(state: VehicleState) -> VehicleState:
            if state.acceleration == 0.0:
                return state
            new_speed_ms = max(
                0.0,
                state.speed_mph * _MPH_TO_MS + state.acceleration * _TICK_DURATION_S,
            )
            return state.model_copy(update={"speed_mph": new_speed_ms * _MS_TO_MPH})

        self._car_highway_state = _update_speed(self._car_highway_state)
        self._car_merge_state = _update_speed(self._car_merge_state)

        # Advance positions along their headings
        def _advance(state: VehicleState) -> VehicleState:
            rad = math.radians(state.heading_degrees)
            vx = math.sin(rad)
            vy = math.cos(rad)
            dist = state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
            return state.model_copy(
                update={
                    "position": Position(
                        x=state.position.x + vx * dist,
                        y=state.position.y + vy * dist,
                    )
                }
            )

        self._car_highway_state = _advance(self._car_highway_state)
        self._car_merge_state = _advance(self._car_merge_state)

        return {
            "CAR_HIGHWAY": self._car_highway_state,
            "CAR_MERGE": self._car_merge_state,
        }

    def _get_new_hazards(self, vehicle_id: str, state: VehicleState) -> list[HazardMessage]:
        """CAR_MERGE injects a merge-conflict hazard whenever TTC gap is tight."""
        if vehicle_id != "CAR_MERGE":
            return []

        hw = self._car_highway_state
        mg = self._car_merge_state

        hw_speed_ms = hw.speed_mph * _MPH_TO_MS
        mg_speed_ms = mg.speed_mph * _MPH_TO_MS

        ttc_hw = _ttc_to_point(
            hw.position.x, hw.position.y, hw_speed_ms, hw.heading_degrees,
            _MERGE_POINT_X, _MERGE_POINT_Y,
        )
        ttc_mg = _ttc_to_point(
            mg.position.x, mg.position.y, mg_speed_ms, mg.heading_degrees,
            _MERGE_POINT_X, _MERGE_POINT_Y,
        )

        if ttc_hw is None or ttc_mg is None:
            return []

        gap = abs(ttc_hw - ttc_mg)

        if gap < _VERY_CLOSE_GAP:
            confidence = 0.95
        elif gap < _CLOSE_GAP:
            confidence = 0.85
        else:
            return []

        return [
            HazardMessage(
                hazard_type=HazardType.ROAD_BLOCKAGE,  # merge conflict zone marker
                source_vehicle="CAR_MERGE",
                road_segment=state.road_segment,
                position=Position(x=_MERGE_POINT_X, y=_MERGE_POINT_Y),
                lane=1,
                confidence=confidence,
                description=(
                    f"merge conflict zone: TTC_highway={ttc_hw:.1f}s "
                    f"TTC_merge={ttc_mg:.1f}s gap={gap:.1f}s"
                ),
                source=InformationSource.SYNTHETIC_SCENARIO,
            )
        ]
