"""Demo 1 — Hidden Pedestrian (watsonx Vision MVP).

CAR_B (observer) analyses a road image at tick 0 and detects a partially-occluded
pedestrian hidden behind a stopped truck. The scene observation is converted to a
HazardMessage and shared with CAR_A (ego, TURN_RIGHT intent). The relevance filter
flags the hazard as relevant because CAR_A is turning right through the same
intersection where the pedestrian was detected → risk = HIGH.
"""
from __future__ import annotations

from app.models import (
    DetectedObject,
    HazardMessage,
    HazardType,
    InformationSource,
    LaneCondition,
    ManeuverZone,
    ObjectType,
    Position,
    SceneObservation,
    VehicleDirection,
    VehicleManeuver,
    VehicleState,
    Visibility,
    VisionSource,
)
from app.scenarios.base import ScenarioBase
from app.scenarios.registry import register

_TICK_DURATION_S = 1.0
_MPH_TO_MS = 0.44704


def _mock_s01_observation() -> SceneObservation:
    """Pre-canned SceneObservation used when watsonx Vision is unavailable."""
    return SceneObservation(
        source_vehicle="CAR_B",
        frame_ref="s01/frame_001.jpg",
        scene_summary=(
            "A truck is stopped partially blocking the right side of the road. "
            "A pedestrian is partially visible behind the truck."
        ),
        observations=[
            DetectedObject(
                type=ObjectType.PEDESTRIAN,
                relative_position="AHEAD_RIGHT",
                visibility=Visibility.PARTIALLY_OCCLUDED,
                occluded_by="truck",
                confidence=0.91,
                source=InformationSource.SYNTHETIC_SCENARIO,
            )
        ],
        lane_conditions={"right_lane": LaneCondition.PARTIALLY_BLOCKED},
        vision_source=VisionSource.MOCK_VISION,
        source=InformationSource.SYNTHETIC_SCENARIO,
    )


@register
class HiddenPedestrianScenario(ScenarioBase):
    """watsonx Vision MVP: CAR_B detects occluded pedestrian → CAR_A risk HIGH."""

    id = "s01"
    name = "Hidden Pedestrian"
    description = (
        "CAR_B analyses a road image and detects a pedestrian partially hidden "
        "behind a truck. The hazard is shared cooperatively; CAR_A (TURN_RIGHT) "
        "is assessed HIGH — VULNERABLE_ROAD_USER / HAZARD_IN_PATH."
    )
    ego_vehicle_id = "CAR_A"

    _car_a_state: VehicleState
    _car_b_state: VehicleState
    _vision_done: bool

    def setup(self) -> None:
        from app.core.reliability_tracker import reliability_tracker

        reliability_tracker._scores["CAR_A"] = 1.0
        reliability_tracker._scores["CAR_B"] = 1.0

        self._vision_done = False

        self.road_images = ["app/static/assets/images/s01/frame_001.jpg"]

        self.zones = [
            ManeuverZone(
                zone_id="Z_S01_INTERSECTION",
                zone_type="TURN",
                road_segment="INTERSECTION_MAIN_OAK",
                center=Position(x=0.0, y=0.0),
                radius_m=100.0,
            )
        ]
        self.store.set_zones(self.zones)

        # CAR_A: ego approaching from the West, TURN_RIGHT at intersection
        self._car_a_state = VehicleState(
            vehicle_id="CAR_A",
            position=Position(x=-20.0, y=0.0),
            road_segment="INTERSECTION_MAIN_OAK",
            speed_mph=30.0,
            acceleration=0.0,
            heading_degrees=90.0,          # East
            direction=VehicleDirection.EAST,
            lane=1,
            target_lane=None,
            intended_maneuver=VehicleManeuver.TURN_RIGHT,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )
        # CAR_B: observer already past the intersection, also heading East
        self._car_b_state = VehicleState(
            vehicle_id="CAR_B",
            position=Position(x=20.0, y=0.0),
            road_segment="INTERSECTION_MAIN_OAK",
            speed_mph=25.0,
            acceleration=0.0,
            heading_degrees=90.0,          # East
            direction=VehicleDirection.EAST,
            lane=1,
            target_lane=None,
            intended_maneuver=VehicleManeuver.KEEP_LANE,
            source=InformationSource.SYNTHETIC_SCENARIO,
            is_simulated=True,
        )

    # ------------------------------------------------------------------
    # Vision analysis: run once at tick 0 for CAR_B
    # ------------------------------------------------------------------

    def _run_vision_for_car_b(self) -> HazardMessage | None:
        """Analyse the road image and return a HazardMessage if an observation is found."""
        from app.core.scene_analyzer import analyze_scene

        obs = analyze_scene(
            frame_ref="s01/frame_001.jpg",
            source_vehicle="CAR_B",
            mock_observation=_mock_s01_observation(),
        )

        if not obs.observations:
            return None

        # Derive HazardMessage from first pedestrian observation
        for detected in obs.observations:
            if detected.type in (ObjectType.PEDESTRIAN,):
                return HazardMessage(
                    hazard_type=HazardType.HIDDEN_PEDESTRIAN,
                    source_vehicle="CAR_B",
                    road_segment="INTERSECTION_MAIN_OAK",
                    position=Position(x=30.0, y=-3.0),   # right side, ahead of CAR_B
                    lane=1,                                # lane 1 — same as CAR_A
                    confidence=detected.confidence,
                    occluded_by=detected.occluded_by,
                    description=obs.scene_summary,
                    source=obs.source,                    # VISION_DERIVED or SYNTHETIC_SCENARIO
                )
        return None

    # ------------------------------------------------------------------
    # Tick logic
    # ------------------------------------------------------------------

    def _advance_vehicles(self) -> dict[str, VehicleState]:
        # Vision analysis happens only at tick 0 (first call to _advance_vehicles)
        if self.tick_index == 0 and not self._vision_done:
            self._vision_done = True
            hazard = self._run_vision_for_car_b()
            if hazard is not None:
                self.store.add_hazard(hazard)

        # Advance CAR_A East (approaching intersection)
        a_dx = self._car_a_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
        self._car_a_state = self._car_a_state.model_copy(
            update={
                "position": Position(
                    x=self._car_a_state.position.x + a_dx,
                    y=self._car_a_state.position.y,
                )
            }
        )

        # Advance CAR_B East
        b_dx = self._car_b_state.speed_mph * _MPH_TO_MS * _TICK_DURATION_S
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
        # The hazard is already injected directly into the store in _advance_vehicles;
        # return empty so the agent does not double-report it.
        return []
