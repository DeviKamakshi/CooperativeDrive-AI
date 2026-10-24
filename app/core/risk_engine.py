"""Deterministic risk engine — always produces LOW / MEDIUM / HIGH.

CRITICAL CONSTRAINTS:
- Never imports from app.watsonx.
- RiskResult.deterministic is ALWAYS True.
- Never sets watsonx_explanation or watsonx_available.
- Pure Python math — no async, no I/O, no network calls.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import uuid4

from app.models import (
    VehicleState,
    HazardMessage,
    CooperativeMessage,
    RiskLevel,
    RiskResult,
    RiskEvidence,
    ReasonCode,
    Recommendation,
    MessageType,
    VehicleManeuver,
    HazardType,
    HazardStatus,
    InformationSource,
)
from app.core.ttc import (
    compute_ttc_to_point,
    compute_vehicle_ttc,
    euclidean_distance,
    mph_to_ms,
    heading_to_vector,
)
from app.core.hazard_expiry import compute_freshness
from app.core.reliability_tracker import reliability_tracker
from app.core.evidence_fusion import compute_fused_confidence_for_hazard
from app.config import settings


# ---------------------------------------------------------------------------
# Hazard severity table
# ---------------------------------------------------------------------------

HAZARD_SEVERITY: dict[HazardType, float] = {
    HazardType.WRONG_WAY_VEHICLE: 1.0,
    HazardType.EMERGENCY_VEHICLE: 0.7,
    HazardType.HIDDEN_PEDESTRIAN: 0.9,
    HazardType.HIDDEN_CYCLIST: 0.85,
    HazardType.SUDDEN_BRAKING: 0.85,
    HazardType.ROAD_DEBRIS: 0.7,
    HazardType.ACCIDENT: 0.8,
    HazardType.ROAD_BLOCKAGE: 0.8,
    HazardType.STOPPED_VEHICLE: 0.65,
    HazardType.DISABLED_VEHICLE: 0.6,
    HazardType.PEDESTRIAN: 0.75,
    HazardType.CYCLIST: 0.7,
    HazardType.STOPPED_TRAFFIC: 0.6,
    HazardType.FAST_APPROACHING_VEHICLE: 0.75,
    HazardType.VEHICLE_IN_BLIND_SPOT: 0.7,
    HazardType.LANE_CLOSURE: 0.5,
    HazardType.CONSTRUCTION: 0.45,
    HazardType.LOW_VISIBILITY: 0.4,
    HazardType.FOG: 0.4,
    HazardType.HEAVY_RAIN: 0.35,
    HazardType.SLIPPERY_ROAD: 0.45,
    HazardType.STANDING_WATER: 0.35,
    HazardType.POTHOLE: 0.4,
}

_LANE_CHANGE_MANEUVERS = {
    VehicleManeuver.CHANGE_LEFT,
    VehicleManeuver.CHANGE_RIGHT,
    VehicleManeuver.MERGE,
    VehicleManeuver.OVERTAKE,
}

_VULNERABLE_ROAD_USER_HAZARDS = {
    HazardType.PEDESTRIAN,
    HazardType.HIDDEN_PEDESTRIAN,
    HazardType.CYCLIST,
    HazardType.HIDDEN_CYCLIST,
}

_CONFLICTED_DISCOUNT = 1.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assess_risk(
    vehicle: VehicleState,
    relevant_hazards: list[HazardMessage],
    active_intent_messages: list[CooperativeMessage],
    max_relevance_distance_m: float | None = None,
) -> RiskResult:
    """Deterministic risk assessment. Returns RiskResult with deterministic=True always.

    Never calls watsonx. Never sets watsonx_explanation or watsonx_available.
    """
    max_dist = (
        max_relevance_distance_m
        if max_relevance_distance_m is not None
        else settings.max_relevance_distance_m
    )

    score = 0.0
    reason_codes: list[ReasonCode] = []
    evidence: list[RiskEvidence] = []
    best_ttc: float | None = None

    # ------------------------------------------------------------------
    # 1. Hazard scoring
    # ------------------------------------------------------------------
    for hazard in relevant_hazards:
        freshness = compute_freshness(hazard.timestamp)
        reliability = reliability_tracker.get_reliability(hazard.source_vehicle)
        fused_conf = compute_fused_confidence_for_hazard(hazard)
        effective_weight = fused_conf * freshness * reliability

        distance_m = euclidean_distance(
            vehicle.position.x, vehicle.position.y,
            hazard.position.x, hazard.position.y,
        )
        distance_factor = _clamp(1.0 - distance_m / max_dist, 0.0, 1.0)

        ttc = compute_ttc_to_point(
            vehicle.position.x, vehicle.position.y,
            vehicle.speed_mph, vehicle.heading_degrees,
            hazard.position.x, hazard.position.y,
        )

        if ttc is not None and ttc <= settings.max_ttc_seconds:
            ttc_factor = _clamp(1.0 - ttc / settings.max_ttc_seconds, 0.0, 1.0)
            # Track the smallest TTC seen
            if best_ttc is None or ttc < best_ttc:
                best_ttc = ttc
        else:
            ttc_factor = distance_factor  # fallback

        severity = HAZARD_SEVERITY.get(hazard.hazard_type, 0.5)

        # Lane overlap
        if vehicle.lane == hazard.lane:
            lane_overlap = 1.0
        elif vehicle.target_lane is not None and vehicle.target_lane == hazard.lane:
            lane_overlap = 1.0
        else:
            lane_overlap = 0.5

        # Conflict discount
        if hazard.status == HazardStatus.CONFLICTED:
            effective_weight *= _CONFLICTED_DISCOUNT

        hazard_score = (
            severity
            * effective_weight
            * max(distance_factor, ttc_factor)
            * lane_overlap
        )

        score = max(score, hazard_score)

        if hazard_score > 0.3:
            codes = _derive_reason_codes(hazard, ttc, fused_conf)
            # Emit TARGET_LANE_HAZARD when the hazard is in the vehicle's target lane
            # (not the current lane) — used by recommendation logic
            if (
                vehicle.target_lane is not None
                and hazard.lane is not None
                and hazard.lane == vehicle.target_lane
                and hazard.lane != vehicle.lane
            ):
                codes.append(ReasonCode.TARGET_LANE_HAZARD)
            reason_codes.extend(codes)
            evidence.append(
                RiskEvidence(
                    evidence_id="EV_" + uuid4().hex[:8].upper(),
                    evidence_type=hazard.hazard_type.value,
                    source_vehicle=hazard.source_vehicle,
                    description=hazard.description or hazard.hazard_type.value,
                    confidence=fused_conf,
                    information_source=hazard.source,
                )
            )

    # ------------------------------------------------------------------
    # 2. Intent conflict scan
    # ------------------------------------------------------------------
    vehicle_changing = vehicle.intended_maneuver in _LANE_CHANGE_MANEUVERS

    for msg in active_intent_messages:
        if msg.message_type != MessageType.INTENT:
            continue
        if msg.source_vehicle == vehicle.vehicle_id:
            continue

        other_target = msg.payload.get("target_lane")
        other_maneuver = msg.payload.get("intended_maneuver")
        other_is_changing = other_maneuver in {m.value for m in _LANE_CHANGE_MANEUVERS}

        if (
            vehicle_changing
            and vehicle.target_lane is not None
            and other_target is not None
            and other_is_changing
            and vehicle.target_lane == other_target
        ):
            # Compute severity from TTC between vehicles if info available
            other_x = msg.position.x
            other_y = msg.position.y
            other_speed = msg.payload.get("speed_mph", 30.0)
            other_heading = msg.payload.get("heading_degrees", vehicle.heading_degrees)

            ttc_intent = compute_vehicle_ttc(
                vehicle.position.x, vehicle.position.y,
                vehicle.speed_mph, vehicle.heading_degrees,
                other_x, other_y,
                float(other_speed), float(other_heading),
                conflict_radius_m=5.0,
            )

            if ttc_intent is not None and ttc_intent <= settings.max_ttc_seconds:
                intent_severity = _clamp(
                    1.0 - ttc_intent / settings.max_ttc_seconds, 0.0, 1.0
                )
                if best_ttc is None or ttc_intent < best_ttc:
                    best_ttc = ttc_intent
            else:
                # Two vehicles both heading to same lane — elevated severity → HIGH
                intent_severity = settings.high_risk_threshold

            score = max(score, intent_severity)
            reason_codes.extend([ReasonCode.INTENT_CONFLICT, ReasonCode.SIMULTANEOUS_LANE_ENTRY])

    # ------------------------------------------------------------------
    # 3. Map score → risk level
    # ------------------------------------------------------------------
    if score >= settings.high_risk_threshold:
        risk = RiskLevel.HIGH
    elif score >= settings.medium_risk_threshold:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    # ------------------------------------------------------------------
    # 4. Derive recommendation
    # ------------------------------------------------------------------
    recommendation = _derive_recommendation(
        risk, vehicle, relevant_hazards, list(dict.fromkeys(reason_codes))
    )

    return RiskResult(
        risk=risk,
        confidence=_clamp(score, 0.0, 1.0),
        reason_codes=list(dict.fromkeys(reason_codes)),  # deduplicate, preserve order
        ttc_seconds=best_ttc,
        evidence=evidence,
        recommendation=recommendation,
        deterministic=True,  # ALWAYS True — never changed
        assessed_vehicle_id=vehicle.vehicle_id,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_reason_codes(
    hazard: HazardMessage,
    ttc: float | None,
    fused_confidence: float,
) -> list[ReasonCode]:
    """Map a hazard to applicable ReasonCodes."""
    codes: list[ReasonCode] = []

    match hazard.hazard_type:
        case HazardType.WRONG_WAY_VEHICLE:
            codes.append(ReasonCode.WRONG_WAY_VEHICLE)
            codes.append(ReasonCode.HEAD_ON_CONFLICT_PREDICTED)
        case HazardType.EMERGENCY_VEHICLE:
            codes.append(ReasonCode.EMERGENCY_VEHICLE_NEARBY)
        case HazardType.SUDDEN_BRAKING:
            codes.append(ReasonCode.SUDDEN_BRAKING_AHEAD)
        case HazardType.VEHICLE_IN_BLIND_SPOT:
            codes.append(ReasonCode.BLIND_SPOT_VEHICLE)
        case _ if hazard.hazard_type in _VULNERABLE_ROAD_USER_HAZARDS:
            codes.append(ReasonCode.VULNERABLE_ROAD_USER)

    if ttc is not None and ttc <= settings.conflict_window_seconds:
        codes.append(ReasonCode.SHORT_TIME_TO_CONFLICT)

    if hazard.confirmation_count > 1:
        codes.append(ReasonCode.MULTIPLE_CONFIRMATIONS)

    if hazard.status == HazardStatus.CONFLICTED:
        codes.append(ReasonCode.CONFLICTING_EVIDENCE)

    if hazard.status == HazardStatus.UNCONFIRMED:
        codes.append(ReasonCode.UNCONFIRMED_HAZARD)

    codes.append(ReasonCode.HAZARD_IN_PATH)

    return codes


def _derive_recommendation(
    risk: RiskLevel,
    vehicle: VehicleState,
    hazards: list[HazardMessage],
    reason_codes: list[ReasonCode],
) -> Recommendation:
    """Derive a recommendation from risk level and scenario context."""
    reason_set = set(reason_codes)
    in_lane_change = vehicle.intended_maneuver in _LANE_CHANGE_MANEUVERS

    if risk == RiskLevel.HIGH:
        # Lane-change abort takes priority: if the hazard is in the target lane
        # (not yet occupied), the safest action is to abort the lane change.
        if in_lane_change and ReasonCode.TARGET_LANE_HAZARD in reason_set:
            return Recommendation.REMAIN_IN_CURRENT_LANE

        if (
            ReasonCode.WRONG_WAY_VEHICLE in reason_set
            or ReasonCode.HEAD_ON_CONFLICT_PREDICTED in reason_set
        ):
            return Recommendation.STOP

        if ReasonCode.SUDDEN_BRAKING_AHEAD in reason_set:
            return Recommendation.INCREASE_FOLLOWING_DISTANCE

        if ReasonCode.VULNERABLE_ROAD_USER in reason_set:
            return Recommendation.REDUCE_SPEED

        # Generic HIGH — if target lane has a hazard and changing lanes, abort
        if in_lane_change:
            return Recommendation.REMAIN_IN_CURRENT_LANE

        return Recommendation.REDUCE_SPEED

    if risk == RiskLevel.MEDIUM:
        return Recommendation.PROCEED_WITH_CAUTION

    return Recommendation.NO_ACTION_REQUIRED
