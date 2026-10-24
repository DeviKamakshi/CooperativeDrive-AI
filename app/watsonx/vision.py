"""watsonx Vision module — ST-08.

Analyzes road images via watsonx Vision and produces SceneObservation.

CRITICAL CONSTRAINTS:
- Prohibited fields are STRIPPED before the observation is used.
- Vision response ONLY contributes VISION_DERIVED qualitative fields.
- Falls back to empty MOCK_VISION observation on any failure.
- Never raises.
"""
from __future__ import annotations

import base64
import sys
from typing import Optional

from app.models import (
    DetectedObject,
    InformationSource,
    LaneCondition,
    ObjectType,
    SceneObservation,
    Visibility,
    VisionSource,
)
from app.watsonx.client import PROHIBITED_VISION_FIELDS, watsonx_client

VISION_SYSTEM_PROMPT = """You are a vehicle safety perception assistant analyzing a road scene image.

Output ONLY valid JSON matching this exact structure:
{
  "scene_summary": "brief description of the scene",
  "observations": [
    {
      "type": "VEHICLE|PEDESTRIAN|CYCLIST|TRUCK|MOTORCYCLE|DEBRIS|CONSTRUCTION_SIGN|ANIMAL|OTHER",
      "relative_position": "AHEAD|AHEAD_LEFT|AHEAD_RIGHT|BEHIND|LEFT|RIGHT",
      "visibility": "CLEAR|PARTIALLY_OCCLUDED|HEAVILY_OCCLUDED|NOT_VISIBLE",
      "occluded_by": "object name or null",
      "confidence": 0.0-1.0
    }
  ],
  "lane_conditions": {
    "left_lane": "CLEAR|PARTIALLY_BLOCKED|BLOCKED|CLOSED|WET|ICY",
    "right_lane": "CLEAR|PARTIALLY_BLOCKED|BLOCKED|CLOSED|WET|ICY",
    "current_lane": "CLEAR|PARTIALLY_BLOCKED|BLOCKED|CLOSED|WET|ICY"
  }
}

IMPORTANT — Do NOT include in your response:
- speed, velocity, mph, kmh
- distance in metres, feet, or any unit
- GPS coordinates, latitude, longitude
- lane numbers
- time to collision or arrival time
- any numeric measurement not explicitly requested above

Only describe what is visually observable. Output JSON only, no other text."""


def analyze_image(
    image_path: str,
    source_vehicle: str,
    frame_ref: str,
) -> SceneObservation:
    """Analyze a road image using watsonx Vision.

    If watsonx Vision is available:
      - Encodes image as base64
      - Calls watsonx_client.analyze_image(image_path, prompt)
      - Parses JSON response
      - Validates and strips prohibited fields
      - Returns SceneObservation with vision_source=WATSONX_VISION, source=VISION_DERIVED

    If unavailable or parse fails:
      - Returns empty SceneObservation with vision_source=MOCK_VISION, source=SYNTHETIC_SCENARIO

    Never raises.
    """
    if not watsonx_client.is_vision_available():
        return _empty_observation(source_vehicle, frame_ref)

    try:
        raw = watsonx_client.analyze_image(image_path, VISION_SYSTEM_PROMPT)
        if raw is None:
            return _empty_observation(source_vehicle, frame_ref)
        return _parse_vision_response(raw, source_vehicle, frame_ref)
    except Exception as exc:  # noqa: BLE001
        print(f"[watsonx_vision] analyze_image error: {exc}", file=sys.stderr)
        return _empty_observation(source_vehicle, frame_ref)


# ---------------------------------------------------------------------------
# Parsing & validation
# ---------------------------------------------------------------------------


def _parse_vision_response(
    raw: dict, source_vehicle: str, frame_ref: str
) -> SceneObservation:
    """Parse watsonx JSON response into SceneObservation.

    Validates each field. Strips prohibited fields. Clamps confidence to [0, 1].
    """
    # Strip prohibited fields at the top level and recursively
    cleaned, stripped_fields = _strip_prohibited_fields(raw)

    scene_summary = str(cleaned.get("scene_summary", "")).strip()

    # Parse observations
    observations: list[DetectedObject] = []
    for item in cleaned.get("observations", []):
        if not isinstance(item, dict):
            continue
        # Strip prohibited fields from each observation item too
        item_clean, item_stripped = _strip_prohibited_fields(item)
        stripped_fields.extend(item_stripped)

        obj_type = _parse_enum(item_clean.get("type"), ObjectType, ObjectType.OTHER)
        relative_position = str(item_clean.get("relative_position", "AHEAD")).upper()
        visibility = _parse_enum(item_clean.get("visibility"), Visibility, Visibility.CLEAR)
        occluded_by = item_clean.get("occluded_by")
        if occluded_by is not None:
            occluded_by = str(occluded_by) if occluded_by != "null" else None
        # Clamp confidence to [0, 1]
        try:
            conf = float(item_clean.get("confidence", 0.8))
            conf = max(0.0, min(1.0, conf))
        except (TypeError, ValueError):
            conf = 0.8

        observations.append(
            DetectedObject(
                type=obj_type,
                relative_position=relative_position,
                visibility=visibility,
                occluded_by=occluded_by,
                confidence=conf,
                source=InformationSource.VISION_DERIVED,
            )
        )

    # Parse lane conditions
    lane_conditions: dict[str, LaneCondition] = {}
    raw_lanes = cleaned.get("lane_conditions", {})
    if isinstance(raw_lanes, dict):
        for lane_key, lane_val in raw_lanes.items():
            condition = _parse_enum(lane_val, LaneCondition, LaneCondition.CLEAR)
            lane_conditions[lane_key] = condition

    return SceneObservation(
        source_vehicle=source_vehicle,
        frame_ref=frame_ref,
        scene_summary=scene_summary,
        observations=observations,
        lane_conditions=lane_conditions,
        vision_source=VisionSource.WATSONX_VISION,
        prohibited_fields_stripped=list(dict.fromkeys(stripped_fields)),
        source=InformationSource.VISION_DERIVED,
    )


def _strip_prohibited_fields(data: dict) -> tuple[dict, list[str]]:
    """Recursively remove prohibited field names from the response dict.

    Returns (cleaned_dict, list_of_stripped_field_names).
    """
    stripped: list[str] = []
    cleaned: dict = {}
    for key, value in data.items():
        if key.lower() in PROHIBITED_VISION_FIELDS:
            stripped.append(key)
            continue
        if isinstance(value, dict):
            sub_cleaned, sub_stripped = _strip_prohibited_fields(value)
            cleaned[key] = sub_cleaned
            stripped.extend(sub_stripped)
        elif isinstance(value, list):
            new_list = []
            for item in value:
                if isinstance(item, dict):
                    item_cleaned, item_stripped = _strip_prohibited_fields(item)
                    new_list.append(item_cleaned)
                    stripped.extend(item_stripped)
                else:
                    new_list.append(item)
            cleaned[key] = new_list
        else:
            cleaned[key] = value
    return cleaned, stripped


def _encode_image_base64(image_path: str) -> Optional[str]:
    """Read image file and return base64-encoded data URI.

    Returns None if file not found or read error.
    """
    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        b64 = base64.b64encode(img_bytes).decode("ascii")
        ext = image_path.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(
            ext, "image/jpeg"
        )
        return f"data:{mime};base64,{b64}"
    except Exception as exc:  # noqa: BLE001
        print(f"[watsonx_vision] encode error: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_observation(source_vehicle: str, frame_ref: str) -> SceneObservation:
    return SceneObservation(
        source_vehicle=source_vehicle,
        frame_ref=frame_ref,
        scene_summary="",
        observations=[],
        lane_conditions={},
        vision_source=VisionSource.MOCK_VISION,
        source=InformationSource.SYNTHETIC_SCENARIO,
    )


def _parse_enum(value: object, enum_class: type, default):
    """Try to parse a string value as an enum member; return default on failure."""
    if value is None:
        return default
    try:
        return enum_class(str(value).upper())
    except (ValueError, KeyError):
        return default
