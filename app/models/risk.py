from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .observation import InformationSource


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReasonCode(str, Enum):
    TARGET_LANE_HAZARD = "TARGET_LANE_HAZARD"
    MULTIPLE_CONFIRMATIONS = "MULTIPLE_CONFIRMATIONS"
    SHORT_TIME_TO_CONFLICT = "SHORT_TIME_TO_CONFLICT"
    INTENT_CONFLICT = "INTENT_CONFLICT"
    SIMULTANEOUS_LANE_ENTRY = "SIMULTANEOUS_LANE_ENTRY"
    WRONG_WAY_VEHICLE = "WRONG_WAY_VEHICLE"
    HEAD_ON_CONFLICT_PREDICTED = "HEAD_ON_CONFLICT_PREDICTED"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    HAZARD_IN_PATH = "HAZARD_IN_PATH"
    INSUFFICIENT_MERGE_GAP = "INSUFFICIENT_MERGE_GAP"
    BLIND_SPOT_VEHICLE = "BLIND_SPOT_VEHICLE"
    VULNERABLE_ROAD_USER = "VULNERABLE_ROAD_USER"
    EMERGENCY_VEHICLE_NEARBY = "EMERGENCY_VEHICLE_NEARBY"
    SUDDEN_BRAKING_AHEAD = "SUDDEN_BRAKING_AHEAD"
    UNCONFIRMED_HAZARD = "UNCONFIRMED_HAZARD"


class Recommendation(str, Enum):
    REMAIN_IN_CURRENT_LANE = "REMAIN_IN_CURRENT_LANE"
    REDUCE_SPEED = "REDUCE_SPEED"
    STOP = "STOP"
    YIELD = "YIELD"
    PROCEED_WITH_CAUTION = "PROCEED_WITH_CAUTION"
    CHANGE_LANE_LEFT = "CHANGE_LANE_LEFT"
    CHANGE_LANE_RIGHT = "CHANGE_LANE_RIGHT"
    INCREASE_FOLLOWING_DISTANCE = "INCREASE_FOLLOWING_DISTANCE"
    NO_ACTION_REQUIRED = "NO_ACTION_REQUIRED"


class ExplanationSource(str, Enum):
    WATSONX = "WATSONX"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"


class RiskEvidence(BaseModel):
    evidence_id: str
    evidence_type: str
    source_vehicle: str
    description: str
    confidence: float
    information_source: InformationSource


class RiskResult(BaseModel):
    risk: RiskLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    ttc_seconds: Optional[float] = None
    evidence: list[RiskEvidence] = Field(default_factory=list)
    recommendation: Recommendation = Recommendation.PROCEED_WITH_CAUTION
    deterministic: bool = True
    watsonx_explanation: Optional[str] = None
    watsonx_available: bool = False
    explanation_source: ExplanationSource = ExplanationSource.DETERMINISTIC_FALLBACK
    assessed_vehicle_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
