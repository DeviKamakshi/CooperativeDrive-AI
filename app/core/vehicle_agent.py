"""Per-vehicle decision engine: determines when to generate cooperative messages."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import (
    CooperativeMessage,
    HazardMessage,
    HazardType,
    InformationSource,
    ManeuverZone,
    MessagePriority,
    MessageType,
    VehicleManeuver,
    VehicleState,
)
from app.core.maneuver_zone import should_share_telemetry
from app.core.evidence_store import EvidenceStore
from app.config import settings

# Hazard type → MessagePriority mapping
HAZARD_PRIORITY: dict[HazardType, MessagePriority] = {
    HazardType.WRONG_WAY_VEHICLE: MessagePriority.URGENT,
    HazardType.EMERGENCY_VEHICLE: MessagePriority.URGENT,
    HazardType.HIDDEN_PEDESTRIAN: MessagePriority.HIGH_PRIORITY,
    HazardType.HIDDEN_CYCLIST: MessagePriority.HIGH_PRIORITY,
    HazardType.SUDDEN_BRAKING: MessagePriority.HIGH_PRIORITY,
    HazardType.ROAD_DEBRIS: MessagePriority.HIGH_PRIORITY,
    HazardType.ACCIDENT: MessagePriority.HIGH_PRIORITY,
    HazardType.ROAD_BLOCKAGE: MessagePriority.HIGH_PRIORITY,
    HazardType.STOPPED_VEHICLE: MessagePriority.HIGH_PRIORITY,
}


class VehicleAgent:
    """Decides when a vehicle should generate cooperative messages.

    Implements the communication trigger rules from the plan:
    - New hazard detected
    - Sudden braking threshold exceeded
    - Vehicle begins/changes a maneuver
    - Telemetry update (when in ManeuverZone or active maneuver)

    Rate limiting: TELEMETRY_UPDATE at most once per telemetry_rate_limit_seconds.
    """

    def __init__(self, vehicle_id: str, store: EvidenceStore) -> None:
        self.vehicle_id = vehicle_id
        self.store = store
        self._last_maneuver: VehicleManeuver | None = None
        self._last_telemetry_broadcast: datetime | None = None
        self._reported_hazards: set[str] = set()  # hazard_ids this agent already reported

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        current_state: VehicleState,
        zones: list[ManeuverZone],
        new_hazards: list[HazardMessage],
        previous_state: VehicleState | None = None,
    ) -> list[CooperativeMessage]:
        """Evaluate current state and return any cooperative messages to send.

        Checks in order:
        1. SUDDEN_BRAKING: acceleration < settings.braking_threshold_ms2
        2. New hazards (from new_hazards list): one HAZARD message per unreported hazard
        3. Maneuver change: INTENT message when maneuver changes or first non-KEEP_LANE tick
        4. Telemetry update (if in zone or active maneuver, rate-limited)
        """
        messages: list[CooperativeMessage] = []

        # 1. Sudden braking
        if current_state.acceleration < settings.braking_threshold_ms2:
            from app.models import HazardStatus
            from datetime import timedelta

            braking_hazard = HazardMessage(
                hazard_type=HazardType.SUDDEN_BRAKING,
                source_vehicle=self.vehicle_id,
                road_segment=current_state.road_segment,
                position=current_state.position,
                lane=current_state.lane,
                confidence=0.95,
                description=f"Sudden braking detected: {current_state.acceleration:.2f} m/s²",
                source=InformationSource.TELEMETRY_DERIVED,
            )
            if braking_hazard.hazard_id not in self._reported_hazards:
                self._reported_hazards.add(braking_hazard.hazard_id)
                self.store.add_hazard(braking_hazard)
                priority = HAZARD_PRIORITY.get(HazardType.SUDDEN_BRAKING, MessagePriority.NORMAL)
                messages.append(self._make_hazard_message(current_state, braking_hazard, priority))

        # 2. New hazards passed in from scene analysis / scenario
        for hazard in new_hazards:
            if hazard.hazard_id not in self._reported_hazards:
                self._reported_hazards.add(hazard.hazard_id)
                self.store.add_hazard(hazard)
                priority = HAZARD_PRIORITY.get(hazard.hazard_type, MessagePriority.NORMAL)
                messages.append(self._make_hazard_message(current_state, hazard, priority))

        # 3. Maneuver change (or first tick with non-KEEP_LANE maneuver)
        current_maneuver = current_state.intended_maneuver
        if previous_state is not None:
            if current_maneuver != previous_state.intended_maneuver:
                messages.append(self._make_intent_message(current_state))
                self._last_maneuver = current_maneuver
        else:
            # First tick: only broadcast if not staying in lane
            if current_maneuver != VehicleManeuver.KEEP_LANE:
                messages.append(self._make_intent_message(current_state))
                self._last_maneuver = current_maneuver

        # 4. Telemetry update (rate-limited)
        if should_share_telemetry(current_state, zones):
            now = datetime.now(timezone.utc)
            if self._last_telemetry_broadcast is None or (
                (now - self._last_telemetry_broadcast).total_seconds()
                >= settings.telemetry_rate_limit_seconds
            ):
                messages.append(self._make_telemetry_message(current_state))
                self._last_telemetry_broadcast = now

        return messages

    # ------------------------------------------------------------------ #
    # Message factories
    # ------------------------------------------------------------------ #

    def _make_hazard_message(
        self,
        vehicle: VehicleState,
        hazard: HazardMessage,
        priority: MessagePriority,
    ) -> CooperativeMessage:
        """Wraps a HazardMessage into a CooperativeMessage."""
        return CooperativeMessage(
            source_vehicle=self.vehicle_id,
            message_type=MessageType.HAZARD,
            priority=priority,
            road_segment=vehicle.road_segment,
            position=vehicle.position,
            lane=vehicle.lane,
            hazard_ref=hazard.hazard_id,
            payload={
                "hazard_type": hazard.hazard_type.value,
                "confidence": hazard.confidence,
                "description": hazard.description,
            },
        )

    def _make_intent_message(self, vehicle: VehicleState) -> CooperativeMessage:
        """Creates an INTENT CooperativeMessage from current vehicle state."""
        return CooperativeMessage(
            source_vehicle=self.vehicle_id,
            message_type=MessageType.INTENT,
            priority=MessagePriority.NORMAL,
            road_segment=vehicle.road_segment,
            position=vehicle.position,
            lane=vehicle.lane,
            payload={
                "intended_maneuver": vehicle.intended_maneuver.value,
                "target_lane": vehicle.target_lane,
                "speed_mph": vehicle.speed_mph,
            },
        )

    def _make_telemetry_message(self, vehicle: VehicleState) -> CooperativeMessage:
        """Creates a TELEMETRY_UPDATE CooperativeMessage."""
        return CooperativeMessage(
            source_vehicle=self.vehicle_id,
            message_type=MessageType.TELEMETRY_UPDATE,
            priority=MessagePriority.LOW_PRIORITY,
            road_segment=vehicle.road_segment,
            position=vehicle.position,
            lane=vehicle.lane,
            payload={
                "speed_mph": vehicle.speed_mph,
                "acceleration": vehicle.acceleration,
                "heading_degrees": vehicle.heading_degrees,
                "intended_maneuver": vehicle.intended_maneuver.value,
            },
        )

    # ------------------------------------------------------------------ #
    # Reset
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Reset agent state (e.g., on scenario restart)."""
        self._last_maneuver = None
        self._last_telemetry_broadcast = None
        self._reported_hazards.clear()
