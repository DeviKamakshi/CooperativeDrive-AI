from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .vehicle import Position


def _message_id() -> str:
    return "MSG_" + uuid4().hex[:8].upper()


def _expires_at_default() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=30)


class MessageType(str, Enum):
    HAZARD = "HAZARD"
    INTENT = "INTENT"
    CONFIRMATION = "CONFIRMATION"
    HAZARD_CLEARED = "HAZARD_CLEARED"
    CONFLICTING_OBSERVATION = "CONFLICTING_OBSERVATION"
    TELEMETRY_UPDATE = "TELEMETRY_UPDATE"


class MessagePriority(str, Enum):
    URGENT = "URGENT"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    NORMAL = "NORMAL"
    LOW_PRIORITY = "LOW_PRIORITY"


class CooperativeMessage(BaseModel):
    message_id: str = Field(default_factory=_message_id)
    source_vehicle: str
    message_type: MessageType
    priority: MessagePriority
    road_segment: str
    position: Position
    lane: Optional[int] = None
    hazard_ref: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    intended_recipients: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(default_factory=_expires_at_default)
