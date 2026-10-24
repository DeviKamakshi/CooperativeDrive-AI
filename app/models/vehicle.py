from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .observation import InformationSource


class VehicleManeuver(str, Enum):
    KEEP_LANE = "KEEP_LANE"
    CHANGE_LEFT = "CHANGE_LEFT"
    CHANGE_RIGHT = "CHANGE_RIGHT"
    MERGE = "MERGE"
    EXIT_HIGHWAY = "EXIT_HIGHWAY"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"
    ENTER_INTERSECTION = "ENTER_INTERSECTION"
    ENTER_ROUNDABOUT = "ENTER_ROUNDABOUT"
    EXIT_ROUNDABOUT = "EXIT_ROUNDABOUT"
    OVERTAKE = "OVERTAKE"
    STOP = "STOP"
    BRAKE = "BRAKE"
    REVERSE = "REVERSE"


class VehicleDirection(str, Enum):
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"
    NORTHEAST = "NORTHEAST"
    NORTHWEST = "NORTHWEST"
    SOUTHEAST = "SOUTHEAST"
    SOUTHWEST = "SOUTHWEST"


class Position(BaseModel):
    x: float
    y: float


class ManeuverZone(BaseModel):
    zone_id: str
    zone_type: str  # MERGE | INTERSECTION | ROUNDABOUT | LANE_CHANGE | EXIT | TURN
    road_segment: str
    center: Position
    radius_m: float = 150.0
    active: bool = True


class VehicleState(BaseModel):
    vehicle_id: str
    position: Position
    road_segment: str
    speed_mph: float
    acceleration: float = 0.0
    heading_degrees: float
    direction: VehicleDirection
    lane: int
    target_lane: Optional[int] = None
    intended_maneuver: VehicleManeuver = VehicleManeuver.KEEP_LANE
    braking: bool = False
    emergency_vehicle: bool = False
    in_maneuver_zone: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: InformationSource
    is_simulated: bool = True
