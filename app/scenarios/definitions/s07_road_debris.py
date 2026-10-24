"""Demo 7 — Road Debris (Multi-Vehicle Confirmation Chain).

CAR_B first spots debris at tick 0 (UNCONFIRMED, confidence=0.72).
CAR_C confirms at tick 3, CAR_D confirms at tick 5 → status CONFIRMED.
CAR_A (ego) risk escalates as confirmations arrive.
"""
from __future__ import annotations

from app.models import (
    HazardMessage,
    HazardStatus,
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

# Debris position (lane 3, ahead)
_DEBRIS_X = 100.0
_DEBRIS_Y = 8.0


@register
class RoadDebrisScenario(ScenarioBase):
    """Three vehicles confirm road debris; CAR_A (ego) risk escalates to HIGH."""

    id = "s07"
    name = "Road Debris"
    description = (
        "CAR_B detects debris at tick 0 (UNCONFIRMED). CAR_C confirms at tick 3; "
        "CAR_D confirms at tick 5 → CONFIRMED. CAR_A (ego) risk HIGH after confirmation."
    )
    ego_vehicle_id = "CAR_A"

    _car_a_state: VehicleState
    _car_b_state: VehicleState
    _car_c_state: VehicleState
    _car_d_state: VehicleState
    _debris_hazard_id: str | None

    def setup(self) -> None:
        from app.core.reliability_tracker import reliability_tracker

        reliability_tracker._scores["CAR_A"] = 1.0
        reliability_tracker._scores["CAR_B"] = 1.0
        reliability_tracker._scores["CAR_C"] = 1.0
        reliability_tracker._scores["CAR_D"] = 1.0

        self._debris_hazard_id = None
        self.road_images = ["app/static/assets/images/s07/frame_001.jpg"]

        self.zones = [
            ManeuverZone(
                zone_id="Z_S07_DEBRIS",
                zone_type="LANE_CHANGE",
                road_segment="HIGHWAY_101_E",
                center=Position(x=0.0, y=8.0),
                radius_m=400.0,
            )
        ]
        self.store.set_zones(self.zones)

        # All vehicles heading East in lane 3 (y=8), in staggered positions
        self._car_b_state = VehicleState(
            vehicle_id="CAR_B",
            position=Position(x=-100.0, y=8.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=60.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=3,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        self._car_c_state = VehicleState(
            vehicle_id="CAR_C",
            position=Position(x=-150.0, y=8.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=55.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=3,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        self._car_d_state = VehicleState(
            vehicle_id="CAR_D",
            position=Position(x=-200.0, y=8.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=50.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=3,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        self._car_a_state = VehicleState(
            vehicle_id="CAR_A",
            position=Position(x=-20.0, y=8.0),
            road_segment="HIGHWAY_101_E",
            speed_mph=65.0,
            acceleration=0.0,
            heading_degrees=90.0,
            direction=VehicleDirection.EAST,
            lane=3,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )

    def _advance_vehicles(self) -> dict[str, VehicleState]:
        # CAR_C confirms at tick 3
        if self.tick_index == 3 and self._debris_hazard_id is not None:
            self.store.confirm_hazard(self._debris_hazard_id, "CAR_C", 0.91)

        # CAR_D confirms at tick 5
        if self.tick_index == 5 and self._debris_hazard_id is not None:
            self.store.confirm_hazard(self._debris_hazard_id, "CAR_D", 0.94)

        def _advance_x(state: VehicleState) -> VehicleState:
            dx = state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
            return state.model_copy(
                update={"position": Position(x=state.position.x + dx, y=state.position.y)}
            )

        self._car_b_state = _advance_x(self._car_b_state)
        self._car_c_state = _advance_x(self._car_c_state)
        self._car_d_state = _advance_x(self._car_d_state)
        self._car_a_state = _advance_x(self._car_a_state)

        return {
            "CAR_A": self._car_a_state,
            "CAR_B": self._car_b_state,
            "CAR_C": self._car_c_state,
            "CAR_D": self._car_d_state,
        }

    def _get_new_hazards(self, vehicle_id: str, state: VehicleState) -> list[HazardMessage]:
        """CAR_B injects the debris hazard exactly once at tick 0."""
        if vehicle_id != "CAR_B" or self.tick_index != 0:
            return []
        if self._debris_hazard_id is not None:
            return []  # already injected

        # Also run scene analysis (for completeness — mirrors the plan)
        try:
            from app.core.scene_analyzer import analyze_scene
            analyze_scene(frame_ref="s07/frame_001.jpg", source_vehicle="CAR_B")
        except Exception:  # noqa: BLE001
            pass

        hazard = HazardMessage(
            hazard_type=HazardType.ROAD_DEBRIS,
            source_vehicle="CAR_B",
            road_segment="HIGHWAY_101_E",
            position=Position(x=_DEBRIS_X, y=_DEBRIS_Y),
            lane=3,
            confidence=0.72,
            description="Road debris detected in lane 3 via camera (UNCONFIRMED)",
            status=HazardStatus.UNCONFIRMED,
            source=InformationSource.VISION_DERIVED,
        )
        self._debris_hazard_id = hazard.hazard_id
        return [hazard]
