"""Demo 3 — Simultaneous Lane Change.

Two vehicles (CAR_A in Lane 1, CAR_B in Lane 3) both attempt to enter Lane 2
at tick 5. The risk engine detects an INTENT_CONFLICT and rates CAR_A HIGH.
"""
from __future__ import annotations

from app.models import (
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
_MPH_TO_MS = 0.44704  # 1 mph in m/s


@register
class SimultaneousLaneChangeScenario(ScenarioBase):
    """Two vehicles simultaneously try to enter Lane 2 from opposite sides."""

    id = "s03"
    name = "Simultaneous Lane Change"
    description = (
        "CAR_A (Lane 1) and CAR_B (Lane 3) both intend to change into Lane 2 "
        "at the same time. Risk engine detects INTENT_CONFLICT → HIGH."
    )
    ego_vehicle_id = "CAR_A"

    # Mutable per-tick state stored as instance attributes
    _car_a_state: VehicleState
    _car_b_state: VehicleState

    def setup(self) -> None:
        from app.core.reliability_tracker import reliability_tracker

        # Pre-trust synthetic vehicles
        reliability_tracker._scores["CAR_A"] = 1.0
        reliability_tracker._scores["CAR_B"] = 1.0

        self.zones = [
            ManeuverZone(
                zone_id="Z_S03_LANE_CHANGE",
                zone_type="LANE_CHANGE",
                road_segment="HIGHWAY_101_E",
                center=Position(x=200.0, y=4.0),
                radius_m=150.0,
            )
        ]
        self.store.set_zones(self.zones)

        self._car_a_state = VehicleState(
            vehicle_id="CAR_A",
            position=Position(x=100.0, y=0.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=55.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=1,
            target_lane=None,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        self._car_b_state = VehicleState(
            vehicle_id="CAR_B",
            position=Position(x=80.0, y=8.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=50.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=3,
            target_lane=None,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )

    def _advance_vehicles(self) -> dict[str, VehicleState]:
        # At tick 5, both vehicles switch to lane-change maneuvers
        if self.tick_index == 5:
            self._car_a_state = self._car_a_state.model_copy(
                update={
                    "intended_maneuver": VehicleManeuver.CHANGE_RIGHT,
                    "target_lane": 2,
                }
            )
            self._car_b_state = self._car_b_state.model_copy(
                update={
                    "intended_maneuver": VehicleManeuver.CHANGE_LEFT,
                    "target_lane": 2,
                }
            )

        # Advance positions East
        a_dx = self._car_a_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
        b_dx = self._car_b_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S

        self._car_a_state = self._car_a_state.model_copy(
            update={
                "position": Position(
                    x=self._car_a_state.position.x + a_dx,
                    y=self._car_a_state.position.y,
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
