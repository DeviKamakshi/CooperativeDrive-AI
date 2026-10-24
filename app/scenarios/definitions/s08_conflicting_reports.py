"""Demo 8 — Conflicting Reports (Responsible AI).

CAR_B reports ROAD_DEBRIS at tick 0 (confidence=0.92). CAR_C drives through the
same area at tick 3 and reports no debris (conflict). Evidence fusion yields
CONFLICTED status; the conflict discount reduces CAR_A's risk from HIGH → MEDIUM
with CONFLICTING_EVIDENCE in reason_codes.
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
# HazardType.ROAD_BLOCKAGE used for the conflicted hazard — severity 0.8 yields MEDIUM after discount
from app.scenarios.base import ScenarioBase
from app.scenarios.registry import register

_TICK_DURATION_S = 1.0
_MPH_TO_MS = 0.44704

# Alleged debris position
_DEBRIS_X = 60.0
_DEBRIS_Y = 0.0


@register
class ConflictingReportsScenario(ScenarioBase):
    """Responsible AI demo: conflicting evidence leaves hazard CONFLICTED → MEDIUM risk."""

    id = "s08"
    name = "Conflicting Reports"
    description = (
        "CAR_B reports debris at (60, 0). CAR_C passes through and reports nothing. "
        "Evidence fusion → CONFLICTED. CAR_A risk drops to MEDIUM with "
        "CONFLICTING_EVIDENCE in reason_codes."
    )
    ego_vehicle_id = "CAR_A"

    _car_a_state: VehicleState
    _car_b_state: VehicleState
    _car_c_state: VehicleState
    _debris_hazard_id: str | None

    def setup(self) -> None:
        from app.core.reliability_tracker import reliability_tracker

        reliability_tracker._scores["CAR_A"] = 1.0
        reliability_tracker._scores["CAR_B"] = 1.0
        reliability_tracker._scores["CAR_C"] = 1.0

        self._debris_hazard_id = None
        self.road_images = ["app/static/assets/images/s08/frame_001.jpg"]

        self.zones = [
            ManeuverZone(
                zone_id="Z_S08_CONFLICT",
                zone_type="LANE_CHANGE",
                road_segment="HIGHWAY_101_E",
                center=Position(x=0.0, y=0.0),
                radius_m=400.0,
            )
        ]
        self.store.set_zones(self.zones)

        self._car_b_state = VehicleState(
            vehicle_id="CAR_B",
            position=Position(x=10.0, y=0.0),
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
            position=Position(x=-20.0, y=0.0),
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
        self._car_a_state = VehicleState(
            vehicle_id="CAR_A",
            position=Position(x=-60.0, y=0.0),
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
        # At tick 3: CAR_C has reached the debris area → file a conflict
        if self.tick_index == 3 and self._debris_hazard_id is not None:
            self.store.conflict_hazard(self._debris_hazard_id, "CAR_C", 0.89)

        def _advance_x(state: VehicleState) -> VehicleState:
            dx = state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
            return state.model_copy(
                update={"position": Position(x=state.position.x + dx, y=state.position.y)}
            )

        self._car_b_state = _advance_x(self._car_b_state)
        self._car_c_state = _advance_x(self._car_c_state)
        self._car_a_state = _advance_x(self._car_a_state)

        return {
            "CAR_A": self._car_a_state,
            "CAR_B": self._car_b_state,
            "CAR_C": self._car_c_state,
        }

    def _get_new_hazards(self, vehicle_id: str, state: VehicleState) -> list[HazardMessage]:
        """CAR_B reports debris at tick 0 exactly once."""
        if vehicle_id != "CAR_B" or self.tick_index != 0:
            return []
        if self._debris_hazard_id is not None:
            return []  # already reported

        hazard = HazardMessage(
            hazard_type=HazardType.ROAD_BLOCKAGE,
            source_vehicle="CAR_B",
            road_segment="HIGHWAY_101_E",
            position=Position(x=_DEBRIS_X, y=_DEBRIS_Y),
            lane=3,
            confidence=0.92,
            description="Road blockage reported in lane 3",
            status=HazardStatus.UNCONFIRMED,
            source=InformationSource.SYNTHETIC_SCENARIO,
        )
        self._debris_hazard_id = hazard.hazard_id
        return [hazard]
