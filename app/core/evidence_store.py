"""Central in-memory evidence store for the cooperative awareness system."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import (
    CooperativeMessage,
    HazardMessage,
    HazardStatus,
    ManeuverZone,
    MessageType,
    VehicleState,
)
from app.core.evidence_fusion import fuse_evidence, compute_fused_confidence_for_hazard
from app.core.hazard_expiry import is_expired
from app.core.reliability_tracker import reliability_tracker


class EvidenceStore:
    """Central in-memory store for the cooperative awareness system.

    Stores:
    - Active vehicle states (keyed by vehicle_id)
    - Active hazards (keyed by hazard_id)
    - Recent cooperative messages (capped list, most recent first)
    - Active maneuver zones

    Provides:
    - Hazard confirmation/conflict updates
    - Expiry cleanup
    - Relevance queries
    """

    def __init__(self, max_messages: int = 200) -> None:
        self._vehicles: dict[str, VehicleState] = {}
        self._hazards: dict[str, HazardMessage] = {}
        self._messages: list[CooperativeMessage] = []
        self._zones: list[ManeuverZone] = []
        self._max_messages = max_messages

    # ------------------------------------------------------------------ #
    # Vehicle state
    # ------------------------------------------------------------------ #

    def update_vehicle(self, state: VehicleState) -> None:
        """Upsert a vehicle state."""
        self._vehicles[state.vehicle_id] = state

    def get_vehicle(self, vehicle_id: str) -> VehicleState | None:
        """Get current state for a vehicle."""
        return self._vehicles.get(vehicle_id)

    def all_vehicles(self) -> dict[str, VehicleState]:
        """Returns copy of vehicle dict."""
        return dict(self._vehicles)

    def remove_vehicle(self, vehicle_id: str) -> None:
        """Remove a vehicle from the store."""
        self._vehicles.pop(vehicle_id, None)

    # ------------------------------------------------------------------ #
    # Hazards
    # ------------------------------------------------------------------ #

    def add_hazard(self, hazard: HazardMessage) -> None:
        """Add a new hazard. If hazard_id already exists, updates it."""
        self._hazards[hazard.hazard_id] = hazard

    def get_hazard(self, hazard_id: str) -> HazardMessage | None:
        """Get hazard by ID."""
        return self._hazards.get(hazard_id)

    def all_hazards(self) -> list[HazardMessage]:
        """Returns list of all non-expired hazards."""
        return [h for h in self._hazards.values() if not is_expired(h.timestamp)]

    def confirm_hazard(
        self, hazard_id: str, vehicle_id: str, confidence: float
    ) -> HazardMessage | None:
        """Record a confirmation from another vehicle.

        Updates confirmation_count, confirming_vehicles, re-runs fuse_evidence,
        updates status. Updates reliability_tracker for the original source.
        Returns updated hazard or None if not found.
        """
        hazard = self._hazards.get(hazard_id)
        if hazard is None:
            return None

        # Avoid double-counting the same confirming vehicle
        if vehicle_id not in hazard.confirming_vehicles:
            hazard.confirming_vehicles.append(vehicle_id)
            hazard.confirmation_count += 1

        # Re-fuse using data already stored on the hazard
        now = datetime.now(timezone.utc)
        confirming = [(vid, hazard.confidence) for vid in hazard.confirming_vehicles]
        conflicting = [(vid, hazard.confidence) for vid in hazard.conflicting_vehicles]
        conf_ts = [now] * len(confirming)
        conf_ct = [now] * len(conflicting)

        result = fuse_evidence(hazard, confirming, conflicting, conf_ts, conf_ct)
        hazard.status = result.status

        reliability_tracker.record_confirmation(hazard.source_vehicle)
        return hazard

    def conflict_hazard(
        self, hazard_id: str, vehicle_id: str, confidence: float
    ) -> HazardMessage | None:
        """Record a conflicting observation.

        Updates conflict_count, conflicting_vehicles, re-runs fuse_evidence,
        updates status. Updates reliability_tracker for the original source.
        Returns updated hazard or None if not found.
        """
        hazard = self._hazards.get(hazard_id)
        if hazard is None:
            return None

        if vehicle_id not in hazard.conflicting_vehicles:
            hazard.conflicting_vehicles.append(vehicle_id)
            hazard.conflict_count += 1

        now = datetime.now(timezone.utc)
        confirming = [(vid, hazard.confidence) for vid in hazard.confirming_vehicles]
        conflicting = [(vid, hazard.confidence) for vid in hazard.conflicting_vehicles]
        conf_ts = [now] * len(confirming)
        conf_ct = [now] * len(conflicting)

        result = fuse_evidence(hazard, confirming, conflicting, conf_ts, conf_ct)
        hazard.status = result.status

        reliability_tracker.record_conflict(hazard.source_vehicle)
        return hazard

    def expire_hazards(self) -> list[str]:
        """Remove all expired hazards. Returns list of expired hazard_ids."""
        expired = [hid for hid, h in self._hazards.items() if is_expired(h.timestamp)]
        for hid in expired:
            del self._hazards[hid]
        return expired

    def hazards_for_vehicle(self, vehicle: VehicleState) -> list[HazardMessage]:
        """Returns non-expired hazards on the same road_segment as vehicle."""
        return [
            h
            for h in self.all_hazards()
            if h.road_segment == vehicle.road_segment
        ]

    # ------------------------------------------------------------------ #
    # Messages
    # ------------------------------------------------------------------ #

    def add_message(self, message: CooperativeMessage) -> None:
        """Prepend to message list, capped at max_messages (oldest dropped)."""
        self._messages.insert(0, message)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[: self._max_messages]

    def recent_messages(self, limit: int = 50) -> list[CooperativeMessage]:
        """Most recent messages, up to limit."""
        return self._messages[:limit]

    def messages_for_vehicle(
        self, vehicle_id: str, limit: int = 20
    ) -> list[CooperativeMessage]:
        """Messages intended for this vehicle (or broadcast) in recency order."""
        result = [
            m
            for m in self._messages
            if not m.intended_recipients or vehicle_id in m.intended_recipients
        ]
        return result[:limit]

    def intent_messages(self) -> list[CooperativeMessage]:
        """All recent INTENT type messages (for risk engine intent conflict scan)."""
        return [m for m in self._messages if m.message_type == MessageType.INTENT]

    # ------------------------------------------------------------------ #
    # Zones
    # ------------------------------------------------------------------ #

    def set_zones(self, zones: list[ManeuverZone]) -> None:
        """Replace active zones for the current scenario."""
        self._zones = list(zones)

    def all_zones(self) -> list[ManeuverZone]:
        """Current active zones."""
        return list(self._zones)

    # ------------------------------------------------------------------ #
    # Reset
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Clear all state. Called when a new scenario starts."""
        self._vehicles.clear()
        self._hazards.clear()
        self._messages.clear()
        self._zones.clear()


# Module-level singleton
evidence_store = EvidenceStore()
