"""Per-vehicle reliability score tracking."""
from __future__ import annotations

_INITIAL_SCORE = 0.80
_MIN_SCORE = 0.20
_MAX_SCORE = 1.0
_DECAY = 0.95
_CONFIRM_TARGET = 1.0
_CONFLICT_TARGET = 0.0


class ReliabilityTracker:
    """Maintains per-vehicle reliability scores.

    Initial score for all vehicles: 0.80
    On confirmation: score = score * 0.95 + 0.05 * 1.0  (nudge toward 1.0)
    On conflict:     score = score * 0.95 + 0.05 * 0.0  (nudge toward 0.0)
    Clamped to [0.2, 1.0].

    Never auto-rejects a report based on reliability alone.
    Reliability is one factor in the risk engine, not a gatekeeper.
    """

    def __init__(self) -> None:
        self._scores: dict[str, float] = {}

    def get_reliability(self, vehicle_id: str) -> float:
        """Return current score. Initialises to 0.80 if not seen before."""
        if vehicle_id not in self._scores:
            self._scores[vehicle_id] = _INITIAL_SCORE
        return self._scores[vehicle_id]

    def record_confirmation(self, vehicle_id: str) -> float:
        """Update score for a confirmed report. Return new score."""
        current = self.get_reliability(vehicle_id)
        updated = current * _DECAY + (1.0 - _DECAY) * _CONFIRM_TARGET
        updated = max(_MIN_SCORE, min(_MAX_SCORE, updated))
        self._scores[vehicle_id] = updated
        return updated

    def record_conflict(self, vehicle_id: str) -> float:
        """Update score for a conflicting report. Return new score."""
        current = self.get_reliability(vehicle_id)
        updated = current * _DECAY + (1.0 - _DECAY) * _CONFLICT_TARGET
        updated = max(_MIN_SCORE, min(_MAX_SCORE, updated))
        self._scores[vehicle_id] = updated
        return updated

    def reset(self, vehicle_id: str) -> None:
        """Reset vehicle to initial score 0.80."""
        self._scores[vehicle_id] = _INITIAL_SCORE

    def reset_all(self) -> None:
        """Clear all reliability scores (resets every vehicle to initial on next lookup)."""
        self._scores.clear()

    def all_scores(self) -> dict[str, float]:
        """Return a copy of all current scores."""
        return dict(self._scores)


reliability_tracker = ReliabilityTracker()
