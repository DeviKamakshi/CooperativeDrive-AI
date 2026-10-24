"""Scene analysis dispatcher — ST-05 mock path + ST-08 watsonx Vision path.

Priority:
  1. watsonx Vision available and returns observations → VISION_DERIVED result
  2. mock_observation provided → SYNTHETIC_SCENARIO mock result
  3. otherwise → minimal empty SYNTHETIC_SCENARIO observation
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import InformationSource, SceneObservation, VisionSource


def analyze_scene_mock(
    frame_ref: str,
    source_vehicle: str,
    mock_observation: SceneObservation,
) -> SceneObservation:
    """Return the provided mock SceneObservation with labels enforced.

    - vision_source set to MOCK_VISION
    - All observation items have source = SYNTHETIC_SCENARIO
    - timestamp set to now
    """
    now = datetime.now(timezone.utc)

    # Enforce source on every detected object
    for obj in mock_observation.observations:
        obj.source = InformationSource.SYNTHETIC_SCENARIO

    # Use model_copy to produce an updated instance (Pydantic v2)
    return mock_observation.model_copy(
        update={
            "frame_ref": frame_ref,
            "vision_source": VisionSource.MOCK_VISION,
            "timestamp": now,
            "source": InformationSource.SYNTHETIC_SCENARIO,
        }
    )


def analyze_scene(
    frame_ref: str,
    source_vehicle: str,
    mock_observation: SceneObservation | None = None,
) -> SceneObservation:
    """Scene analysis dispatcher.

    1. If watsonx Vision is available (client.is_vision_available()):
       → call watsonx/vision.py analyze_image()
       → if result has observations: return it (VISION_DERIVED)
       → if result is empty (vision call returned nothing useful): fall through
    2. If mock_observation is provided: return it via analyze_scene_mock()
    3. Otherwise: return empty SceneObservation (SYNTHETIC_SCENARIO)
    """
    # -- Watsonx Vision path (ST-08) --
    try:
        from app.watsonx.client import watsonx_client
        from app.watsonx import vision as watsonx_vision

        if watsonx_client.is_vision_available():
            result = watsonx_vision.analyze_image(frame_ref, source_vehicle, frame_ref)
            if result.observations:
                return result
            # Empty result — fall through to mock / empty
    except Exception:  # noqa: BLE001
        pass  # vision module unavailable; continue to mock path

    # -- Mock path --
    if mock_observation is not None:
        return analyze_scene_mock(frame_ref, source_vehicle, mock_observation)

    # -- Minimal empty observation --
    return SceneObservation(
        source_vehicle=source_vehicle,
        frame_ref=frame_ref,
        scene_summary="",
        observations=[],
        lane_conditions={},
        vision_source=VisionSource.MOCK_VISION,
        timestamp=datetime.now(timezone.utc),
        source=InformationSource.SYNTHETIC_SCENARIO,
    )
