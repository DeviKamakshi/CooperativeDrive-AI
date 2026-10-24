"""Base class and frame dataclass for CooperativeDrive scenario simulations."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.models import (
    CooperativeMessage,
    HazardMessage,
    ManeuverZone,
    MessageType,
    RiskResult,
    VehicleState,
)


@dataclass
class ScenarioFrame:
    """Snapshot of scenario state at one tick."""

    scenario_id: str
    scenario_name: str
    tick: int
    vehicles: dict[str, dict]       # vehicle_id → VehicleState.model_dump()
    messages_this_tick: list[dict]  # CooperativeMessage.model_dump() list
    active_hazards: list[dict]      # HazardMessage.model_dump() list
    risk_result: dict | None        # RiskResult.model_dump() for ego vehicle, or None
    zones: list[dict]               # ManeuverZone.model_dump() list
    ego_vehicle_id: str             # which vehicle the risk result is for
    description: str = ""           # human-readable scenario description
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def model_dump(self, **kwargs: Any) -> dict:
        """Return dict representation (mirrors Pydantic API for compatibility)."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "tick": self.tick,
            "vehicles": self.vehicles,
            "messages_this_tick": self.messages_this_tick,
            "active_hazards": self.active_hazards,
            "risk_result": self.risk_result,
            "zones": self.zones,
            "ego_vehicle_id": self.ego_vehicle_id,
            "description": self.description,
            "timestamp": self.timestamp,
        }


class ScenarioBase:
    """Base class for all CooperativeDrive scenarios.

    Subclasses implement:
    - setup(): initialises vehicle states, zones, tick_index
    - _advance_vehicles(): returns updated vehicle states for each tick

    Framework handles:
    - Storing vehicle states in evidence_store
    - Running VehicleAgent for each vehicle
    - Passing messages through relevance_filter
    - Running risk engine for ego vehicle
    """

    id: str = "base"
    name: str = "Base Scenario"
    description: str = ""
    ego_vehicle_id: str = "CAR_A"

    def __init__(self) -> None:
        from app.core.evidence_store import evidence_store
        from app.core.vehicle_agent import VehicleAgent  # noqa: F401

        self.store = evidence_store
        self._agents: dict[str, Any] = {}
        self.tick_index: int = 0
        self._previous_states: dict[str, VehicleState] = {}
        self.zones: list[ManeuverZone] = []
        self.road_images: list[str] = []

    def setup(self) -> None:
        """Override: initialise vehicle states and zones. Called once before first tick."""
        raise NotImplementedError

    def _advance_vehicles(self) -> dict[str, VehicleState]:
        """Override: compute vehicle positions/states for this tick.
        Returns dict of vehicle_id → VehicleState."""
        raise NotImplementedError

    def _get_new_hazards(self, vehicle_id: str, state: VehicleState) -> list[HazardMessage]:
        """Override if scenario injects hazards at specific ticks. Default: empty."""
        return []

    def tick(self) -> ScenarioFrame:
        """Run one simulation step. Framework method — do not override."""
        from app.core.relevance_filter import filter_recipients
        from app.core.risk_engine import assess_risk

        # 1. Advance vehicle positions
        new_states = self._advance_vehicles()

        # 2. For each vehicle: run agent, collect messages
        all_messages: list[CooperativeMessage] = []
        for vid, state in new_states.items():
            prev = self._previous_states.get(vid)
            new_hazards = self._get_new_hazards(vid, state)

            agent = self._get_or_create_agent(vid)
            messages = agent.evaluate(state, self.zones, new_hazards, prev)

            for msg in messages:
                recipients = filter_recipients(msg, new_states, self.zones, vid)
                msg.intended_recipients = recipients
                self.store.add_message(msg)
                all_messages.append(msg)

            self.store.update_vehicle(state)
            self._previous_states[vid] = state

        # 3. Risk assessment for ego vehicle
        ego_state = new_states.get(self.ego_vehicle_id)
        risk_result: RiskResult | None = None
        if ego_state:
            hazards = self.store.hazards_for_vehicle(ego_state)
            intents = self.store.intent_messages()
            risk_result = assess_risk(ego_state, hazards, intents)

        self.tick_index += 1

        return ScenarioFrame(
            scenario_id=self.id,
            scenario_name=self.name,
            tick=self.tick_index,
            vehicles={vid: s.model_dump(mode="json") for vid, s in new_states.items()},
            messages_this_tick=[m.model_dump(mode="json") for m in all_messages],
            active_hazards=[h.model_dump(mode="json") for h in self.store.all_hazards()],
            risk_result=risk_result.model_dump(mode="json") if risk_result else None,
            zones=[z.model_dump(mode="json") for z in self.zones],
            ego_vehicle_id=self.ego_vehicle_id,
            description=self.description,
        )

    def reset(self) -> None:
        """Reset scenario to initial state."""
        from app.core.reliability_tracker import reliability_tracker

        self.tick_index = 0
        self._previous_states = {}
        self._agents = {}
        self.store.reset()
        reliability_tracker.reset_all()

    def get_metadata(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ego_vehicle_id": self.ego_vehicle_id,
        }

    def _get_or_create_agent(self, vehicle_id: str) -> Any:
        from app.core.vehicle_agent import VehicleAgent

        if vehicle_id not in self._agents:
            self._agents[vehicle_id] = VehicleAgent(vehicle_id, self.store)
        return self._agents[vehicle_id]
