"""Multi-vehicle evidence fusion for hazard confirmation and conflict handling."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models import HazardMessage, HazardStatus, InformationSource
from app.core.hazard_expiry import compute_freshness
from app.core.reliability_tracker import reliability_tracker

_EPSILON = 1e-6


@dataclass
class FusionResult:
    status: HazardStatus
    fused_confidence: float
    positive_score: float
    negative_score: float
    confirmation_count: int
    conflict_count: int


def fuse_evidence(
    hazard: HazardMessage,
    confirming_confidences: list[tuple[str, float]],  # (vehicle_id, confidence)
    conflicting_confidences: list[tuple[str, float]],  # (vehicle_id, confidence)
    confirming_timestamps: list[datetime],
    conflicting_timestamps: list[datetime],
) -> FusionResult:
    """Fuse evidence from multiple vehicles about a hazard.

    The original hazard is always counted in positive_score.
    confirming_confidences/timestamps are *additional* vehicles beyond the original.

    Algorithm
    ---------
    positive_score = original contribution
                   + sum(conf * reliability * freshness for each confirming report)

    negative_score = sum(conf * reliability * freshness for each conflicting report)

    Status rules (checked in order):
      LIKELY_CLEARED : negative_score > positive_score * 1.2
      CONFIRMED      : len(confirming) >= 1 AND positive_score > 0.7
      CONFLICTED     : negative_score > 0 AND positive_score > 0
      UNCONFIRMED    : otherwise

    fused_confidence = positive_score / (positive_score + negative_score + epsilon)
    """
    # Original hazard contribution to positive score
    orig_reliability = reliability_tracker.get_reliability(hazard.source_vehicle)
    orig_freshness = compute_freshness(hazard.timestamp)
    positive_score = hazard.confidence * orig_reliability * orig_freshness

    # Confirming reports
    for (vid, conf), ts in zip(confirming_confidences, confirming_timestamps):
        rel = reliability_tracker.get_reliability(vid)
        fresh = compute_freshness(ts)
        positive_score += conf * rel * fresh

    # Conflicting reports
    negative_score = 0.0
    for (vid, conf), ts in zip(conflicting_confidences, conflicting_timestamps):
        rel = reliability_tracker.get_reliability(vid)
        fresh = compute_freshness(ts)
        negative_score += conf * rel * fresh

    fused_confidence = positive_score / (positive_score + negative_score + _EPSILON)

    # Status determination (order matters)
    if negative_score > positive_score * 1.2:
        status = HazardStatus.LIKELY_CLEARED
    elif len(confirming_confidences) >= 1 and positive_score > 0.7:
        status = HazardStatus.CONFIRMED
    elif negative_score > 0 and positive_score > 0:
        status = HazardStatus.CONFLICTED
    else:
        status = HazardStatus.UNCONFIRMED

    return FusionResult(
        status=status,
        fused_confidence=fused_confidence,
        positive_score=positive_score,
        negative_score=negative_score,
        confirmation_count=len(confirming_confidences),
        conflict_count=len(conflicting_confidences),
    )


def compute_fused_confidence_for_hazard(hazard: HazardMessage) -> float:
    """Convenience: compute fused confidence from data already on the HazardMessage.

    Uses confirmation_count and conflict_count as approximations when full
    per-report timestamps are unavailable. Returns hazard.confidence if no
    additional confirmations.
    """
    if hazard.confirmation_count <= 1 and hazard.conflict_count == 0:
        return hazard.confidence

    orig_reliability = reliability_tracker.get_reliability(hazard.source_vehicle)
    orig_freshness = compute_freshness(hazard.timestamp)
    positive_score = hazard.confidence * orig_reliability * orig_freshness

    # Extra confirmations: approximate with hazard.confidence and current freshness
    extra_confirmations = max(0, hazard.confirmation_count - 1)
    for vid in hazard.confirming_vehicles[:extra_confirmations]:
        rel = reliability_tracker.get_reliability(vid)
        positive_score += hazard.confidence * rel * orig_freshness

    # Conflicts: approximate symmetrically
    negative_score = 0.0
    for vid in hazard.conflicting_vehicles:
        rel = reliability_tracker.get_reliability(vid)
        negative_score += hazard.confidence * rel * orig_freshness

    return positive_score / (positive_score + negative_score + _EPSILON)
