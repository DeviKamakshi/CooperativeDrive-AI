from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .observation import InformationSource
from .vehicle import Position


def _hazard_id() -> str:
    return "HZD_" + uuid4().hex[:8].upper()


def _expires_at_default() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=120)


class HazardType(str, Enum):
    # Vehicles
    STOPPED_VEHICLE = "STOPPED_VEHICLE"
    DISABLED_VEHICLE = "DISABLED_VEHICLE"
    SUDDEN_BRAKING = "SUDDEN_BRAKING"
    WRONG_WAY_VEHICLE = "WRONG_WAY_VEHICLE"
    FAST_APPROACHING_VEHICLE = "FAST_APPROACHING_VEHICLE"
    VEHICLE_IN_BLIND_SPOT = "VEHICLE_IN_BLIND_SPOT"
    # Road users
    PEDESTRIAN = "PEDESTRIAN"
    HIDDEN_PEDESTRIAN = "HIDDEN_PEDESTRIAN"
    CYCLIST = "CYCLIST"
    HIDDEN_CYCLIST = "HIDDEN_CYCLIST"
    # Road hazards
    ROAD_DEBRIS = "ROAD_DEBRIS"
    POTHOLE = "POTHOLE"
    ACCIDENT = "ACCIDENT"
    STOPPED_TRAFFIC = "STOPPED_TRAFFIC"
    LANE_CLOSURE = "LANE_CLOSURE"
    CONSTRUCTION = "CONSTRUCTION"
    ROAD_BLOCKAGE = "ROAD_BLOCKAGE"
    # Environmental
    SLIPPERY_ROAD = "SLIPPERY_ROAD"
    LOW_VISIBILITY = "LOW_VISIBILITY"
    FOG = "FOG"
    HEAVY_RAIN = "HEAVY_RAIN"
    STANDING_WATER = "STANDING_WATER"
    # Special
    EMERGENCY_VEHICLE = "EMERGENCY_VEHICLE"


class HazardStatus(str, Enum):
    UNCONFIRMED = "UNCONFIRMED"
    CONFIRMED = "CONFIRMED"
    CONFLICTED = "CONFLICTED"
    LIKELY_CLEARED = "LIKELY_CLEARED"
    EXPIRED = "EXPIRED"


class HazardMessage(BaseModel):
    hazard_id: str = Field(default_factory=_hazard_id)
    hazard_type: HazardType
    source_vehicle: str
    road_segment: str
    position: Position
    lane: Optional[int] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    occluded_by: Optional[str] = None
    description: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(default_factory=_expires_at_default)
    confirmation_count: int = 1
    conflict_count: int = 0
    status: HazardStatus = HazardStatus.UNCONFIRMED
    source: InformationSource
    confirming_vehicles: list[str] = Field(default_factory=list)
    conflicting_vehicles: list[str] = Field(default_factory=list)
