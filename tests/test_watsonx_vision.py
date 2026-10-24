"""Unit tests for app/watsonx/vision.py — 5 tests, all mocked."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.models import (
    InformationSource,
    VisionSource,
)
from app.watsonx.vision import (
    _encode_image_base64,
    _parse_vision_response,
    _strip_prohibited_fields,
    analyze_image,
)


# ---------------------------------------------------------------------------
# 1. Vision unavailable → returns empty MOCK_VISION observation
# ---------------------------------------------------------------------------


def test_vision_unavailable_returns_empty_observation():
    """When vision is disabled, analyze_image returns empty MOCK_VISION observation."""
    with patch("app.watsonx.vision.watsonx_client") as mock_client:
        mock_client.is_vision_available.return_value = False
        result = analyze_image("/fake/image.jpg", "V1", "frame-001")

    assert result.vision_source == VisionSource.MOCK_VISION
    assert result.source == InformationSource.SYNTHETIC_SCENARIO
    assert result.observations == []
    assert result.scene_summary == ""


# ---------------------------------------------------------------------------
# 2. Prohibited fields are stripped from vision response
# ---------------------------------------------------------------------------


def test_prohibited_fields_stripped():
    """Vision response containing 'speed' and 'distance_m' → those absent from result."""
    raw_response = {
        "scene_summary": "Highway scene",
        "speed": 65,              # PROHIBITED
        "distance_m": 40.0,       # PROHIBITED
        "observations": [
            {
                "type": "VEHICLE",
                "relative_position": "AHEAD",
                "visibility": "CLEAR",
                "occluded_by": None,
                "confidence": 0.9,
                "speed_mph": 55,   # PROHIBITED nested
            }
        ],
        "lane_conditions": {
            "current_lane": "CLEAR",
        },
    }

    cleaned, stripped = _strip_prohibited_fields(raw_response)

    assert "speed" not in cleaned
    assert "distance_m" not in cleaned
    assert "speed" in stripped
    assert "distance_m" in stripped

    # Nested prohibited field in observations
    assert "speed_mph" not in cleaned["observations"][0]
    assert "speed_mph" in stripped


# ---------------------------------------------------------------------------
# 3. Valid vision response is parsed into correct SceneObservation structure
# ---------------------------------------------------------------------------


def test_valid_vision_response_parsed():
    """Valid JSON response → correct SceneObservation, VISION_DERIVED source."""
    raw = {
        "scene_summary": "Busy intersection with pedestrians",
        "observations": [
            {
                "type": "PEDESTRIAN",
                "relative_position": "AHEAD_LEFT",
                "visibility": "PARTIALLY_OCCLUDED",
                "occluded_by": "truck",
                "confidence": 0.88,
            },
            {
                "type": "VEHICLE",
                "relative_position": "AHEAD",
                "visibility": "CLEAR",
                "occluded_by": None,
                "confidence": 0.95,
            },
        ],
        "lane_conditions": {
            "left_lane": "CLEAR",
            "right_lane": "WET",
            "current_lane": "CLEAR",
        },
    }

    result = _parse_vision_response(raw, "V2", "frame-042")

    assert result.source == InformationSource.VISION_DERIVED
    assert result.vision_source == VisionSource.WATSONX_VISION
    assert result.source_vehicle == "V2"
    assert result.frame_ref == "frame-042"
    assert result.scene_summary == "Busy intersection with pedestrians"
    assert len(result.observations) == 2
    assert result.observations[0].confidence == 0.88
    assert result.observations[0].occluded_by == "truck"
    assert result.observations[1].confidence == 0.95
    assert len(result.lane_conditions) == 3


# ---------------------------------------------------------------------------
# 4. Malformed JSON in vision response → fallback observation, no crash
# ---------------------------------------------------------------------------


def test_vision_parse_error_returns_fallback():
    """When watsonx returns malformed data (e.g. non-dict), analyze_image returns fallback."""
    with patch("app.watsonx.vision.watsonx_client") as mock_client:
        mock_client.is_vision_available.return_value = True
        # analyze_image on the client returns None (simulate JSON parse failure)
        mock_client.analyze_image.return_value = None

        result = analyze_image("/fake/image.png", "V3", "frame-bad")

    assert result.vision_source == VisionSource.MOCK_VISION
    assert result.source == InformationSource.SYNTHETIC_SCENARIO
    assert result.observations == []


# ---------------------------------------------------------------------------
# 5. _encode_image_base64 returns None for missing file
# ---------------------------------------------------------------------------


def test_encode_image_missing_file_returns_none():
    """_encode_image_base64 returns None when the file does not exist."""
    result = _encode_image_base64("/this/path/does/not/exist.jpg")
    assert result is None
