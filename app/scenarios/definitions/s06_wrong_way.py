"""Demo 6 — Wrong-Way Vehicle.

CAR_WRONG drives West on an Eastbound highway. CAR_A (ego) is heading East and is
directly in CAR_WRONG's path. CAR_B is behind CAR_WRONG (already past it, heading
East) and should NOT receive the warning.

Wrong-way detection: heading deviates from expected road direction (90° East) by > 150°.
CAR_A's agent synthesises a WRONG_WAY_VEHICLE hazard and the relevance filter ensures
only CAR_A (not CAR_B) is in intended_recipients.
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

# Expected road direction for HIGHWAY_101_E (degrees)
_EXPECTED_HEADING = 90.0  # East
_WRONG_WAY_THRESHOLD = 150.0  # degrees deviation that constitutes wrong-way


def _heading_deviation(heading: float, expected: float) -> float:
    """Absolute angular difference between two headings (0–180°)."""
    diff = abs((heading - expected + 360) % 360)
    if diff > 180:
        diff = 360 - diff
    return diff


@register
class WrongWayScenario(ScenarioBase):
    """Wrong-way vehicle detected; only vehicles in its path are warned."""

    id = "s06"
    name = "Wrong-Way Vehicle"
    description = (
        "CAR_WRONG travels West on an Eastbound road. CAR_A (ego) is in its "
        "direct path → HIGH risk. CAR_B is already past the danger zone and "
        "is excluded by the relevance filter."
    )
    ego_vehicle_id = "CAR_A"

    _car_wrong_state: VehicleState
    _car_a_state: VehicleState
    _car_b_state: VehicleState

    def setup(self) -> None:
        from app.core.reliability_tracker import reliability_tracker

        # Pre-trust synthetic vehicles
        reliability_tracker._scores["CAR_A"] = 1.0
        reliability_tracker._scores["CAR_B"] = 1.0
        reliability_tracker._scores["CAR_WRONG"] = 1.0

        self.zones = [
            ManeuverZone(
                zone_id="Z_S06_HEADON",
                zone_type="INTERSECTION",
                road_segment="HIGHWAY_101_E",
                center=Position(x=200.0, y=0.0),
                radius_m=300.0,
            )
        ]
        self.store.set_zones(self.zones)

        self._car_wrong_state = VehicleState(
            vehicle_id="CAR_WRONG",
            position=Position(x=200.0, y=0.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=60.0,
            acceleration=0.0,
            heading_degrees=270.0,     # West — wrong-way
            direction=VehicleDirection.WEST,
            lane=1,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        self._car_a_state = VehicleState(
            vehicle_id="CAR_A",
            position=Position(x=100.0, y=0.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=65.0,
            acceleration=0.0,
            heading_degrees=90.0,      # East (correct)
            direction=VehicleDirection.EAST,
            lane=1,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        # CAR_B starts east of CAR_WRONG — already past the danger zone heading East
        self._car_b_state = VehicleState(
            vehicle_id="CAR_B",
            position=Position(x=400.0, y=0.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=60.0,
            acceleration=0.0,
            heading_degrees=90.0,      # East (correct)
            direction=VehicleDirection.EAST,
            lane=1,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )

    def _advance_vehicles(self) -> dict[str, VehicleState]:
        # CAR_WRONG moves West (x decreases)
        wrong_dx = -(self._car_wrong_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S)
        # CAR_A and CAR_B move East (x increases)
        a_dx = self._car_a_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
        b_dx = self._car_b_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S

        self._car_wrong_state = self._car_wrong_state.model_copy(
            update={
                "position": Position(
                    x=self._car_wrong_state.position.x + wrong_dx,
                    y=self._car_wrong_state.position.y,
                )
            }
        )
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
            "CAR_WRONG": self._car_wrong_state,
        }

    def _get_new_hazards(self, vehicle_id: str, state: VehicleState) -> list[HazardMessage]:
        """CAR_A detects any vehicle whose heading deviates > 150° from road direction."""
        if vehicle_id != "CAR_A":
            return []

        hazards: list[HazardMessage] = []
        for other_id, other_state in [
            ("CAR_WRONG", self._car_wrong_state),
            ("CAR_B", self._car_b_state),
        ]:
            deviation = _heading_deviation(other_state.heading_degrees, _EXPECTED_HEADING)
            if deviation > _WRONG_WAY_THRESHOLD:
                hazards.append(
                    HazardMessage(
                        hazard_type=HazardType.WRONG_WAY_VEHICLE,
                        source_vehicle="CAR_A",
                        road_segment=state.road_segment,
                        position=other_state.position,
                        lane=other_state.lane,
                        confidence=0.98,
                        description=(
                            f"{other_id} is heading {other_state.heading_degrees}° "
                            f"on an Eastbound road (deviation={deviation:.0f}°)"
                        ),
                        source=InformationSource.SYNTHETIC_SCENARIO,
                    )
                )
        return hazards
