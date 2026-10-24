"""Unit tests for app/core/scene_analyzer.py"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import (
    DetectedObject,
    InformationSource,
    ObjectType,
    SceneObservation,
    VisionSource,
    Visibility,
)
from app.core.scene_analyzer import analyze_scene, analyze_scene_mock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_observation(
    source_vehicle: str = "V1",
    with_objects: bool = False,
) -> SceneObservation:
    objects = []
    if with_objects:
        objects = [
            DetectedObject(
                type=ObjectType.PEDESTRIAN,
                relative_position="ahead",
                visibility=Visibility.PARTIALLY_OCCLUDED,
                confidence=0.85,
                source=InformationSource.VISION_DERIVED,  # should be overwritten
            )
        ]
    return SceneObservation(
        source_vehicle=source_vehicle,
        scene_summary="Test scene",
        observations=objects,
        source=InformationSource.VISION_DERIVED,  # should be overwritten
        vision_source=VisionSource.WATSONX_VISION,  # should be overwritten
    )


# ---------------------------------------------------------------------------
# 1. Mock path → vision_source == MOCK_VISION
# ---------------------------------------------------------------------------

def test_mock_path_sets_mock_vision_source():
    """analyze_scene_mock enforces VisionSource.MOCK_VISION."""
    obs = _make_observation()
    result = analyze_scene_mock("frame-001", "V1", obs)
    assert result.vision_source == VisionSource.MOCK_VISION


# ---------------------------------------------------------------------------
# 2. Mock path → all observations have source == SYNTHETIC_SCENARIO
# ---------------------------------------------------------------------------

def test_mock_path_sets_synthetic_scenario_source():
    """analyze_scene_mock sets source=SYNTHETIC_SCENARIO on all detected objects."""
    obs = _make_observation(with_objects=True)
    result = analyze_scene_mock("frame-001", "V1", obs)
    for obj in result.observations:
        assert obj.source == InformationSource.SYNTHETIC_SCENARIO


# ---------------------------------------------------------------------------
# 3. Mock path → timestamp is recent (set to now)
# ---------------------------------------------------------------------------

def test_mock_path_updates_timestamp():
    """analyze_scene_mock updates the observation timestamp to approximately now."""
    before = datetime.now(timezone.utc)
    obs = _make_observation()
    result = analyze_scene_mock("frame-001", "V1", obs)
    after = datetime.now(timezone.utc)
    assert before <= result.timestamp <= after


# ---------------------------------------------------------------------------
# 4. analyze_scene without mock returns minimal empty SceneObservation
# ---------------------------------------------------------------------------

def test_analyze_scene_without_mock_returns_empty():
    """analyze_scene(mock_observation=None) returns a minimal empty observation."""
    result = analyze_scene("frame-002", "V2", mock_observation=None)
    assert result.source_vehicle == "V2"
    assert result.frame_ref == "frame-002"
    assert result.observations == []
    assert result.source == InformationSource.SYNTHETIC_SCENARIO
    assert result.vision_source == VisionSource.MOCK_VISION
    assert result.scene_summary == ""
