"""Unit tests for app/watsonx/explainer.py — 8 tests, all mocked."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.models import (
    ExplanationSource,
    InformationSource,
    ReasonCode,
    Recommendation,
    RiskEvidence,
    RiskLevel,
    RiskResult,
)
from app.watsonx.explainer import explain_risk, _deterministic_explanation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_risk_result(
    risk: RiskLevel = RiskLevel.HIGH,
    confidence: float = 0.85,
    reason_codes: list[ReasonCode] | None = None,
    ttc_seconds: float | None = None,
    assessed_vehicle_id: str = "V1",
) -> RiskResult:
    return RiskResult(
        risk=risk,
        confidence=confidence,
        reason_codes=reason_codes or [],
        ttc_seconds=ttc_seconds,
        evidence=[],
        recommendation=Recommendation.PROCEED_WITH_CAUTION,
        deterministic=True,
        assessed_vehicle_id=assessed_vehicle_id,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. Deterministic fallback — HIGH INTENT_CONFLICT contains "HIGH" and "lane"
# ---------------------------------------------------------------------------


def test_deterministic_explanation_high_intent_conflict():
    """HIGH + INTENT_CONFLICT → fallback explanation contains 'HIGH' and 'lane'."""
    rr = _make_risk_result(
        risk=RiskLevel.HIGH,
        reason_codes=[ReasonCode.INTENT_CONFLICT],
    )
    with patch("app.watsonx.explainer.watsonx_client") as mock_client:
        mock_client.is_text_available.return_value = False
        result = explain_risk(rr)

    assert "HIGH" in result.watsonx_explanation
    assert "lane" in result.watsonx_explanation.lower()
    assert result.explanation_source == ExplanationSource.DETERMINISTIC_FALLBACK


# ---------------------------------------------------------------------------
# 2. Deterministic fallback — HIGH WRONG_WAY contains "wrong-way"
# ---------------------------------------------------------------------------


def test_deterministic_explanation_high_wrong_way():
    """HIGH + WRONG_WAY_VEHICLE → fallback explanation contains 'wrong-way'."""
    rr = _make_risk_result(
        risk=RiskLevel.HIGH,
        reason_codes=[ReasonCode.WRONG_WAY_VEHICLE],
    )
    with patch("app.watsonx.explainer.watsonx_client") as mock_client:
        mock_client.is_text_available.return_value = False
        result = explain_risk(rr)

    assert "wrong-way" in result.watsonx_explanation.lower()
    assert result.explanation_source == ExplanationSource.DETERMINISTIC_FALLBACK


# ---------------------------------------------------------------------------
# 3. Deterministic fallback — LOW risk → "No significant hazards"
# ---------------------------------------------------------------------------


def test_deterministic_explanation_low():
    """LOW risk → fallback explanation starts with 'No significant hazards'."""
    rr = _make_risk_result(risk=RiskLevel.LOW, confidence=0.1)
    with patch("app.watsonx.explainer.watsonx_client") as mock_client:
        mock_client.is_text_available.return_value = False
        result = explain_risk(rr)

    assert "No significant hazards" in result.watsonx_explanation
    assert result.explanation_source == ExplanationSource.DETERMINISTIC_FALLBACK


# ---------------------------------------------------------------------------
# 4. Deterministic fallback — TTC is included when set
# ---------------------------------------------------------------------------


def test_deterministic_explanation_includes_ttc():
    """When ttc_seconds is set, fallback explanation includes the TTC value."""
    rr = _make_risk_result(
        risk=RiskLevel.HIGH,
        reason_codes=[ReasonCode.SUDDEN_BRAKING_AHEAD],
        ttc_seconds=3.7,
    )
    explanation = _deterministic_explanation(rr)
    assert "3.7" in explanation


# ---------------------------------------------------------------------------
# 5. watsonx explanation used when available
# ---------------------------------------------------------------------------


def test_watsonx_explanation_used_when_available():
    """When watsonx returns a string, explanation_source == WATSONX."""
    rr = _make_risk_result(risk=RiskLevel.MEDIUM, confidence=0.5)
    with patch("app.watsonx.explainer.watsonx_client") as mock_client:
        mock_client.is_text_available.return_value = True
        mock_client.generate_text.return_value = "Potential hazard ahead. Proceed with caution."
        result = explain_risk(rr)

    assert result.explanation_source == ExplanationSource.WATSONX
    assert result.watsonx_available is True
    assert "hazard" in result.watsonx_explanation.lower()


# ---------------------------------------------------------------------------
# 6. watsonx failure falls back gracefully — no crash
# ---------------------------------------------------------------------------


def test_watsonx_failure_falls_back():
    """If watsonx raises an exception, falls back to deterministic, no crash."""
    rr = _make_risk_result(risk=RiskLevel.HIGH, reason_codes=[ReasonCode.INTENT_CONFLICT])
    with patch("app.watsonx.explainer.watsonx_client") as mock_client:
        mock_client.is_text_available.return_value = True
        mock_client.generate_text.side_effect = RuntimeError("connection refused")
        result = explain_risk(rr)

    assert result.explanation_source == ExplanationSource.DETERMINISTIC_FALLBACK
    assert result.watsonx_available is False
    assert result.watsonx_explanation is not None
    assert len(result.watsonx_explanation) > 0


# ---------------------------------------------------------------------------
# 7. risk level never modified by explain_risk
# ---------------------------------------------------------------------------


def test_risk_level_never_modified():
    """explain_risk() must not change risk_result.risk."""
    for level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH):
        rr = _make_risk_result(risk=level)
        with patch("app.watsonx.explainer.watsonx_client") as mock_client:
            mock_client.is_text_available.return_value = False
            result = explain_risk(rr)
        assert result.risk == level


# ---------------------------------------------------------------------------
# 8. deterministic flag stays True after explain_risk
# ---------------------------------------------------------------------------


def test_deterministic_flag_unchanged():
    """RiskResult.deterministic must remain True after explain_risk()."""
    rr = _make_risk_result(risk=RiskLevel.HIGH)
    assert rr.deterministic is True
    with patch("app.watsonx.explainer.watsonx_client") as mock_client:
        mock_client.is_text_available.return_value = True
        mock_client.generate_text.return_value = "Some watsonx explanation text here."
        result = explain_risk(rr)
    assert result.deterministic is True
