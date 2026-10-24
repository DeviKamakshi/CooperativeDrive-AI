"""Scenario registry — register, look up, and list CooperativeDrive scenarios."""
from __future__ import annotations

from app.scenarios.base import ScenarioBase

_registry: dict[str, type[ScenarioBase]] = {}


def register(cls: type[ScenarioBase]) -> type[ScenarioBase]:
    """Decorator to register a scenario class by its ``id`` attribute."""
    _registry[cls.id] = cls
    return cls


def get_scenario(scenario_id: str) -> ScenarioBase | None:
    """Return a fresh instance of the scenario, or None if not found."""
    cls = _registry.get(scenario_id)
    return cls() if cls else None


def list_scenarios() -> list[dict]:
    """Return metadata dicts for all registered scenarios."""
    return [cls().get_metadata() for cls in _registry.values()]


# ---------------------------------------------------------------------------
# Import scenario definitions to trigger @register decoration
# ---------------------------------------------------------------------------
from app.scenarios.definitions import s01_hidden_pedestrian  # noqa: F401, E402
from app.scenarios.definitions import s02_highway_merge  # noqa: F401, E402
from app.scenarios.definitions import s03_simultaneous_lane_change  # noqa: F401, E402
from app.scenarios.definitions import s04_blind_intersection  # noqa: F401, E402
from app.scenarios.definitions import s05_sudden_braking  # noqa: F401, E402
from app.scenarios.definitions import s06_wrong_way  # noqa: F401, E402
from app.scenarios.definitions import s07_road_debris  # noqa: F401, E402
from app.scenarios.definitions import s08_conflicting_reports  # noqa: F401, E402
