"""watsonx Explanation module — ST-08.

Adds a natural-language explanation to a RiskResult.

CRITICAL CONSTRAINTS:
- NEVER modifies risk_result.risk, risk_result.confidence, or risk_result.deterministic.
- deterministic stays True forever.
- Only sets watsonx_explanation, watsonx_available, explanation_source.
- Falls back silently on any watsonx failure.
"""
from __future__ import annotations

from app.models import ExplanationSource, ReasonCode, RiskLevel, RiskResult
from app.watsonx.client import watsonx_client

SYSTEM_PROMPT = """You are a cooperative vehicle safety assistant.
You receive structured evidence about a detected risk and produce a concise driver advisory.

Rules you MUST follow:
1. Use ONLY the evidence provided in the input. Do not invent any facts.
2. Maximum 2 sentences.
3. Do not change the risk level (LOW/MEDIUM/HIGH).
4. If confidence is below 0.75, communicate uncertainty (e.g. "may", "possible", "reported").
5. Never invent distances, speeds, hazard types, or vehicle counts not present in the input.
6. Write for a driver — clear, plain language, no technical jargon.
7. Do not say "I" or refer to yourself.
"""


def explain_risk(risk_result: RiskResult) -> RiskResult:
    """Adds a natural-language explanation to a RiskResult.

    If watsonx is available: calls generate_text with structured evidence summary.
    If unavailable or call fails: generates deterministic fallback explanation.

    NEVER modifies risk_result.risk, risk_result.confidence, or risk_result.deterministic.
    Returns the same RiskResult object with watsonx_explanation and watsonx_available set.
    """
    evidence_summary = _build_evidence_summary(risk_result)

    explanation = _call_watsonx_explainer(evidence_summary, risk_result)
    if explanation is None:
        explanation = _deterministic_explanation(risk_result)
        risk_result.explanation_source = ExplanationSource.DETERMINISTIC_FALLBACK
        risk_result.watsonx_available = False
    else:
        risk_result.explanation_source = ExplanationSource.WATSONX
        risk_result.watsonx_available = True

    risk_result.watsonx_explanation = explanation
    return risk_result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_evidence_summary(risk_result: RiskResult) -> str:
    """Converts RiskResult to a compact text summary for the prompt."""
    lines = [
        f"Risk level: {risk_result.risk.value}",
        f"Confidence: {risk_result.confidence:.2f}",
    ]

    if risk_result.reason_codes:
        codes = ", ".join(rc.value for rc in risk_result.reason_codes)
        lines.append(f"Reason codes: {codes}")

    if risk_result.ttc_seconds is not None:
        lines.append(f"Time to conflict: {risk_result.ttc_seconds:.1f} seconds")

    if risk_result.evidence:
        lines.append("Evidence:")
        for ev in risk_result.evidence[:5]:  # cap at 5 items
            lines.append(
                f"  - [{ev.evidence_type}] from {ev.source_vehicle}: "
                f"{ev.description} (confidence {ev.confidence:.2f})"
            )

    lines.append(f"Recommended action: {risk_result.recommendation.value}")
    return "\n".join(lines)


def _call_watsonx_explainer(
    evidence_summary: str, risk_result: RiskResult
) -> str | None:
    """Calls watsonx text generation. Returns text or None."""
    if not watsonx_client.is_text_available():
        return None

    prompt = (
        f"Generate a 1-2 sentence driver advisory for the following risk assessment:\n\n"
        f"{evidence_summary}\n\n"
        f"Advisory:"
    )

    try:
        result = watsonx_client.generate_text(prompt, system_prompt=SYSTEM_PROMPT, max_new_tokens=120)
        if result and len(result.strip()) > 5:
            return result.strip()
        return None
    except Exception:  # noqa: BLE001
        return None


def _deterministic_explanation(risk_result: RiskResult) -> str:
    """Generates a rule-based fallback explanation from structured data."""
    risk = risk_result.risk
    reason_set = set(risk_result.reason_codes)
    confidence = risk_result.confidence
    ttc = risk_result.ttc_seconds

    # Build base message from reason codes
    if risk == RiskLevel.HIGH:
        if ReasonCode.WRONG_WAY_VEHICLE in reason_set:
            base = "HIGH risk: wrong-way vehicle detected ahead. Do not proceed."
        elif ReasonCode.INTENT_CONFLICT in reason_set:
            base = "HIGH risk: two vehicles intend to enter the same lane simultaneously."
        elif ReasonCode.TARGET_LANE_HAZARD in reason_set:
            base = "HIGH risk: target lane contains a recently confirmed hazard."
        elif ReasonCode.SUDDEN_BRAKING_AHEAD in reason_set:
            base = "HIGH risk: sudden braking detected ahead. Increase following distance."
        elif ReasonCode.VULNERABLE_ROAD_USER in reason_set:
            base = "HIGH risk: pedestrian or cyclist detected near your intended path."
        else:
            base = "HIGH risk: hazard confirmed ahead. Immediate caution required."
    elif risk == RiskLevel.MEDIUM:
        if ReasonCode.CONFLICTING_EVIDENCE in reason_set:
            base = "MEDIUM risk: vehicle reports disagree about road conditions ahead."
        else:
            base = "MEDIUM risk: hazard reported ahead. Proceed with caution."
    else:
        base = "No significant hazards detected on current path."

    # Append TTC if available and risk is not LOW
    if ttc is not None and risk != RiskLevel.LOW:
        ttc_text = f" Time to conflict: {ttc:.1f} seconds."
        # Avoid double period
        if base.endswith("."):
            base = base[:-1] + "." + ttc_text
        else:
            base = base + ttc_text

    # Append uncertainty qualifier when confidence is low
    if confidence < 0.75 and risk != RiskLevel.LOW:
        if not any(word in base for word in ("may", "possible", "reported", "reported")):
            base = base.replace("detected", "possibly detected", 1)

    return base
