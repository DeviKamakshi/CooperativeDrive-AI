"""Demo 5 — Sudden Braking Chain.

CAR_C (front) brakes hard at tick 5. The warning propagates C→B→A.
CAR_A (ego, rear) receives the hazard message and is assessed HIGH.
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
_MPH_TO_MS = 0.44704   # 1 mph → m/s
_MS_TO_MPH = 2.23694   # 1 m/s → mph

# Braking accelerations (m/s²)
_BRAKE_C = -6.1   # sharp braking, below threshold (-4.0)
_BRAKE_B = -3.0   # reactive braking by CAR_B (above threshold, just slowing)


@register
class SuddenBrakingScenario(ScenarioBase):
    """CAR_C brakes hard; the hazard message propagates back through the convoy."""

    id = "s05"
    name = "Sudden Braking Chain"
    description = (
        "CAR_C brakes hard at tick 5. The SUDDEN_BRAKING hazard propagates "
        "C→B→A. CAR_A (ego) is assessed HIGH with SUDDEN_BRAKING_AHEAD."
    )
    ego_vehicle_id = "CAR_A"

    _car_a_state: VehicleState
    _car_b_state: VehicleState
    _car_c_state: VehicleState

    def setup(self) -> None:
        from app.core.reliability_tracker import reliability_tracker

        # Pre-trust synthetic vehicles so telemetry-derived hazards score correctly
        reliability_tracker._scores["CAR_C"] = 1.0
        reliability_tracker._scores["CAR_B"] = 1.0
        reliability_tracker._scores["CAR_A"] = 1.0

        self.zones = [
            ManeuverZone(
                zone_id="Z_S05_CONVOY",
                zone_type="LANE_CHANGE",
                road_segment="HIGHWAY_101_E",
                center=Position(x=200.0, y=0.0),
                radius_m=200.0,
            )
        ]
        self.store.set_zones(self.zones)

        self._car_c_state = VehicleState(
            vehicle_id="CAR_C",
            position=Position(x=140.0, y=0.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=65.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=1,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        self._car_b_state = VehicleState(
            vehicle_id="CAR_B",
            position=Position(x=110.0, y=0.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=60.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=1,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        self._car_a_state = VehicleState(
            vehicle_id="CAR_A",
            position=Position(x=80.0, y=0.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=58.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=1,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )

    def _advance_vehicles(self) -> dict[str, VehicleState]:
        # At tick 5: apply braking to CAR_C and reactive braking to CAR_B
        if self.tick_index == 5:
            self._car_c_state = self._car_c_state.model_copy(
                update={
                    "acceleration": _BRAKE_C,
                    "braking": True,
                    "intended_maneuver": VehicleManeuver.BRAKE,
                }
            )
            self._car_b_state = self._car_b_state.model_copy(
                update={
                    "acceleration": _BRAKE_B,
                    "braking": True,
                }
            )

        # Apply acceleration to speeds (clamp to 0)
        def _update_speed(state: VehicleState) -> VehicleState:
            if state.acceleration == 0.0:
                return state
            new_speed_ms = max(
                0.0,
                state.speed_mph * _MPH_TO_MS + state.acceleration * _TICK_DURATION_S,
            )
            return state.model_copy(update={"speed_mph": new_speed_ms * _MS_TO_MPH})

        self._car_c_state = _update_speed(self._car_c_state)
        self._car_b_state = _update_speed(self._car_b_state)
        self._car_a_state = _update_speed(self._car_a_state)

        # Advance positions East
        def _advance_x(state: VehicleState) -> VehicleState:
            dx = state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
            return state.model_copy(
                update={"position": Position(x=state.position.x + dx, y=state.position.y)}
            )

        self._car_c_state = _advance_x(self._car_c_state)
        self._car_b_state = _advance_x(self._car_b_state)
        self._car_a_state = _advance_x(self._car_a_state)

        return {
            "CAR_A": self._car_a_state,
            "CAR_B": self._car_b_state,
            "CAR_C": self._car_c_state,
        }
