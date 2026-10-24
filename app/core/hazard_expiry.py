"""Hazard freshness and expiry calculations."""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings


def linear_interp(value: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """Linear interpolation. Clamps result to [min(y0,y1), max(y0,y1)]."""
    if x1 == x0:
        return y0
    result = y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    lo, hi = min(y0, y1), max(y0, y1)
    return max(lo, min(hi, result))


def compute_freshness(timestamp: datetime, now: datetime | None = None) -> float:
    """Return freshness 0.0–1.0 based on observation age.

    Bands (configurable via settings):
      0 – FRESHNESS_FULL_SECONDS:       1.0
      FULL – MODERATE_SECONDS:          linear 1.0 → 0.6
      MODERATE – EXPIRY_SECONDS:        linear 0.6 → 0.0
      > EXPIRY_SECONDS:                 0.0 (expired)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    age = (now - timestamp).total_seconds()

    full = settings.freshness_full_seconds
    moderate = settings.freshness_moderate_seconds
    expiry = settings.hazard_expiry_seconds

    if age <= full:
        return 1.0
    if age <= moderate:
        return linear_interp(age, full, moderate, 1.0, 0.6)
    if age <= expiry:
        return linear_interp(age, moderate, expiry, 0.6, 0.0)
    return 0.0


def is_expired(timestamp: datetime, now: datetime | None = None) -> bool:
    """Return True if compute_freshness returns 0.0."""
    return compute_freshness(timestamp, now) == 0.0
