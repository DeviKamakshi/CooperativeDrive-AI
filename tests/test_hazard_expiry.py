"""Unit tests for app/core/hazard_expiry.py"""
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.core.hazard_expiry import compute_freshness, is_expired, linear_interp

# Convenience shortcuts from settings
FULL = settings.freshness_full_seconds
MODERATE = settings.freshness_moderate_seconds
EXPIRY = settings.hazard_expiry_seconds

_BASE = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _ts(age_seconds: float) -> datetime:
    """Return a timestamp that is age_seconds old relative to _BASE."""
    return _BASE - timedelta(seconds=age_seconds)


def test_freshness_at_zero_seconds():
    """Age 0 s → freshness 1.0."""
    ts = _ts(0)
    assert compute_freshness(ts, now=_BASE) == pytest.approx(1.0)


def test_freshness_at_full_boundary():
    """Age == FRESHNESS_FULL_SECONDS → freshness 1.0."""
    ts = _ts(FULL)
    assert compute_freshness(ts, now=_BASE) == pytest.approx(1.0)


def test_freshness_midway_moderate():
    """Age == (FULL + MODERATE) / 2 → approximately 0.8."""
    mid = (FULL + MODERATE) / 2.0
    ts = _ts(mid)
    result = compute_freshness(ts, now=_BASE)
    assert result == pytest.approx(0.8, abs=1e-9)


def test_freshness_at_moderate_boundary():
    """Age == FRESHNESS_MODERATE_SECONDS → freshness 0.6."""
    ts = _ts(MODERATE)
    assert compute_freshness(ts, now=_BASE) == pytest.approx(0.6)


def test_freshness_midway_expiry():
    """Age == (MODERATE + EXPIRY) / 2 → approximately 0.3."""
    mid = (MODERATE + EXPIRY) / 2.0
    ts = _ts(mid)
    result = compute_freshness(ts, now=_BASE)
    assert result == pytest.approx(0.3, abs=1e-9)


def test_freshness_at_expiry_boundary():
    """Age == HAZARD_EXPIRY_SECONDS → freshness 0.0."""
    ts = _ts(EXPIRY)
    assert compute_freshness(ts, now=_BASE) == pytest.approx(0.0)


def test_freshness_past_expiry():
    """Age > EXPIRY + 10 s → freshness 0.0."""
    ts = _ts(EXPIRY + 10.0)
    assert compute_freshness(ts, now=_BASE) == 0.0


def test_is_expired_false():
    """Fresh hazard (age 0) is not expired."""
    ts = _ts(0)
    assert is_expired(ts, now=_BASE) is False


def test_is_expired_true():
    """Old hazard (past expiry) is expired."""
    ts = _ts(EXPIRY + 1.0)
    assert is_expired(ts, now=_BASE) is True
