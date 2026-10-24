"""Tests for app/core/evidence_fusion.py — 7 tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import (
    HazardMessage,
    HazardType,
    HazardStatus,
    InformationSource,
    Position,
)
from app.core.evidence_fusion import fuse_evidence, compute_fused_confidence_for_hazard
from app.core.reliability_tracker import ReliabilityTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_hazard(
    confidence: float = 0.8,
    source_vehicle: str = "CAR_A",
    status: HazardStatus = HazardStatus.UNCONFIRMED,
    confirmation_count: int = 1,
    conflict_count: int = 0,
    confirming_vehicles: list[str] | None = None,
    conflicting_vehicles: list[str] | None = None,
) -> HazardMessage:
    return HazardMessage(
        hazard_type=HazardType.STOPPED_VEHICLE,
        source_vehicle=source_vehicle,
        road_segment="SEG_1",
        position=Position(x=100.0, y=200.0),
        confidence=confidence,
        source=InformationSource.SYNTHETIC_SCENARIO,
        status=status,
        confirmation_count=confirmation_count,
        conflict_count=conflict_count,
        confirming_vehicles=confirming_vehicles or [],
        conflicting_vehicles=conflicting_vehicles or [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_single_report_unconfirmed():
    """One original report, no additional confirmations → UNCONFIRMED."""
    hazard = _make_hazard(confidence=0.6)
    result = fuse_evidence(
        hazard,
        confirming_confidences=[],
        conflicting_confidences=[],
        confirming_timestamps=[],
        conflicting_timestamps=[],
    )
    assert result.status == HazardStatus.UNCONFIRMED
    assert result.confirmation_count == 0
    assert result.conflict_count == 0
    assert result.negative_score == 0.0
    assert result.positive_score > 0.0


def test_single_confirmation_confirmed():
    """Original high-confidence + one confirming with high score → CONFIRMED."""
    hazard = _make_hazard(confidence=0.9)
    now = _now()
    result = fuse_evidence(
        hazard,
        confirming_confidences=[("CAR_B", 0.9)],
        conflicting_confidences=[],
        confirming_timestamps=[now],
        conflicting_timestamps=[],
    )
    assert result.status == HazardStatus.CONFIRMED
    assert result.confirmation_count == 1
    assert result.positive_score > 0.7


def test_conflicting_evidence():
    """Original high confidence + matching conflicting confidence → CONFLICTED."""
    hazard = _make_hazard(confidence=0.85)
    now = _now()
    result = fuse_evidence(
        hazard,
        confirming_confidences=[],
        conflicting_confidences=[("CAR_C", 0.85)],
        confirming_timestamps=[],
        conflicting_timestamps=[now],
    )
    assert result.status == HazardStatus.CONFLICTED
    assert result.positive_score > 0.0
    assert result.negative_score > 0.0


def test_likely_cleared():
    """Original low confidence + strong conflicting → LIKELY_CLEARED."""
    hazard = _make_hazard(confidence=0.3)
    now = _now()
    result = fuse_evidence(
        hazard,
        confirming_confidences=[],
        conflicting_confidences=[("CAR_D", 0.95), ("CAR_E", 0.95)],
        confirming_timestamps=[],
        conflicting_timestamps=[now, now],
    )
    assert result.status == HazardStatus.LIKELY_CLEARED
    assert result.negative_score > result.positive_score * 1.2


def test_fused_confidence_increases_with_confirmations():
    """More confirming vehicles → higher fused_confidence."""
    hazard = _make_hazard(confidence=0.7)
    now = _now()

    result_one = fuse_evidence(
        hazard,
        confirming_confidences=[("CAR_B", 0.7)],
        conflicting_confidences=[],
        confirming_timestamps=[now],
        conflicting_timestamps=[],
    )
    result_three = fuse_evidence(
        hazard,
        confirming_confidences=[("CAR_B", 0.7), ("CAR_C", 0.7), ("CAR_D", 0.7)],
        conflicting_confidences=[],
        confirming_timestamps=[now, now, now],
        conflicting_timestamps=[],
    )
    assert result_three.fused_confidence > result_one.fused_confidence


def test_fused_confidence_decreases_with_conflicts():
    """Adding a conflicting report decreases fused_confidence compared to no conflict."""
    hazard = _make_hazard(confidence=0.8)
    now = _now()

    result_no_conflict = fuse_evidence(
        hazard,
        confirming_confidences=[],
        conflicting_confidences=[],
        confirming_timestamps=[],
        conflicting_timestamps=[],
    )
    result_with_conflict = fuse_evidence(
        hazard,
        confirming_confidences=[],
        conflicting_confidences=[("CAR_X", 0.8)],
        confirming_timestamps=[],
        conflicting_timestamps=[now],
    )
    assert result_with_conflict.fused_confidence < result_no_conflict.fused_confidence


def test_conflict_discount_in_fused_confidence():
    """A CONFLICTED-status hazard has lower fused_confidence than one with a confirmer."""
    # Hazard with one confirmation (positive_score high enough → CONFIRMED)
    hazard_conf = _make_hazard(confidence=0.9)
    now = _now()

    confirmed_result = fuse_evidence(
        hazard_conf,
        confirming_confidences=[("CAR_B", 0.9)],
        conflicting_confidences=[],
        confirming_timestamps=[now],
        conflicting_timestamps=[],
    )

    # Same hazard but with a strong conflicting report → CONFLICTED
    hazard_conflict = _make_hazard(confidence=0.9)
    conflicted_result = fuse_evidence(
        hazard_conflict,
        confirming_confidences=[],
        conflicting_confidences=[("CAR_C", 0.85)],
        confirming_timestamps=[],
        conflicting_timestamps=[now],
    )

    # CONFIRMED hazard has higher fused_confidence than CONFLICTED
    assert confirmed_result.fused_confidence > conflicted_result.fused_confidence
    assert conflicted_result.status == HazardStatus.CONFLICTED
    assert confirmed_result.status == HazardStatus.CONFIRMED
