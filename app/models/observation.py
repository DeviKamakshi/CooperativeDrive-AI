from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class InformationSource(str, Enum):
    VISION_DERIVED = "VISION_DERIVED"
    TELEMETRY_DERIVED = "TELEMETRY_DERIVED"
    SYNTHETIC_SCENARIO = "SYNTHETIC_SCENARIO"


class VisionSource(str, Enum):
    WATSONX_VISION = "WATSONX_VISION"
    MOCK_VISION = "MOCK_VISION"


class ObjectType(str, Enum):
    VEHICLE = "VEHICLE"
    PEDESTRIAN = "PEDESTRIAN"
    CYCLIST = "CYCLIST"
    TRUCK = "TRUCK"
    MOTORCYCLE = "MOTORCYCLE"
    DEBRIS = "DEBRIS"
    CONSTRUCTION_SIGN = "CONSTRUCTION_SIGN"
    ANIMAL = "ANIMAL"
    OTHER = "OTHER"


class Visibility(str, Enum):
    CLEAR = "CLEAR"
    PARTIALLY_OCCLUDED = "PARTIALLY_OCCLUDED"
    HEAVILY_OCCLUDED = "HEAVILY_OCCLUDED"
    NOT_VISIBLE = "NOT_VISIBLE"


class LaneCondition(str, Enum):
    CLEAR = "CLEAR"
    PARTIALLY_BLOCKED = "PARTIALLY_BLOCKED"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"
    WET = "WET"
    ICY = "ICY"


class DetectedObject(BaseModel):
    type: ObjectType
    relative_position: str
    visibility: Visibility = Visibility.CLEAR
    occluded_by: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: InformationSource = InformationSource.VISION_DERIVED


class SceneObservation(BaseModel):
    source_vehicle: str
    frame_ref: Optional[str] = None
    scene_summary: str
    observations: list[DetectedObject] = Field(default_factory=list)
    lane_conditions: dict[str, LaneCondition] = Field(default_factory=dict)
    vision_source: VisionSource = VisionSource.MOCK_VISION
    prohibited_fields_stripped: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: InformationSource = InformationSource.VISION_DERIVED
