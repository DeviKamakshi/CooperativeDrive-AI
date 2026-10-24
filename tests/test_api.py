"""Unit and API tests for CooperativeDrive AI FastAPI backend."""
import io
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from main import app
from vision import vision_analyzer
from PIL import Image

client = TestClient(app)


def test_status_endpoint():
    """Tests /api/status endpoint response."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("CONNECTED", "OFFLINE")
    assert "message" in data


def test_assess_json_pedestrian_scenario():
    """Manual Test 2: CAR_A, 30 mph, Lane 2, TURN_RIGHT, Pedestrian observation."""
    payload = {
        "vehicle_id": "CAR_A",
        "speed": "30 mph",
        "current_lane": "2",
        "target_lane": "2",
        "direction": "EAST",
        "intended_maneuver": "TURN_RIGHT",
        "source_vehicle": "CAR_B",
        "observation": "Pedestrian partially hidden behind stopped truck ahead-right. Moving toward roadway. Confidence 92%.",
    }
    response = client.post("/api/assess", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk"] == "HIGH"
    assert "pedestrian" in data["hazard"].lower()
    assert "CAR_A" in data["recipients"]
    assert data["confidence"] in ("HIGH", "MEDIUM")


def test_assess_json_debris_scenario():
    """Manual Test 1: CAR_A, 60 mph, Lane 2, Target Lane 3, CHANGE_RIGHT, Debris in lane 3."""
    payload = {
        "vehicle_id": "CAR_A",
        "speed": "60 mph",
        "current_lane": "2",
        "target_lane": "3",
        "direction": "EAST",
        "intended_maneuver": "CHANGE_RIGHT",
        "source_vehicle": "CAR_B",
        "observation": "Road debris ahead in lane 3. Confidence 94%.",
    }
    response = client.post("/api/assess", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk"] == "HIGH"
    assert "debris" in data["hazard"].lower()
    assert "CAR_A" in data["recipients"]


def test_assess_json_clear_road_scenario():
    """Manual Test 3: CAR_A, 30 mph, KEEP_LANE, Road ahead clear."""
    payload = {
        "vehicle_id": "CAR_A",
        "speed": "30 mph",
        "current_lane": "2",
        "target_lane": "2",
        "direction": "EAST",
        "intended_maneuver": "KEEP_LANE",
        "source_vehicle": "CAR_B",
        "observation": "Road ahead clear. No nearby hazards reported.",
    }
    response = client.post("/api/assess", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk"] == "LOW"


def test_assess_missing_observation():
    """Assess should fail with 400 when observation is empty."""
    payload = {
        "vehicle_id": "CAR_A",
        "observation": "",
    }
    response = client.post("/api/assess", json=payload)
    assert response.status_code == 400


def test_image_validation_valid():
    """Tests image validation on a valid generated PNG."""
    img = Image.new("RGB", (64, 64), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    content = buf.getvalue()

    valid, err = vision_analyzer.validate_image_file("test.png", content)
    assert valid is True
    assert err == ""

    res = vision_analyzer.analyze_image(content, "pedestrian_crossing.png")
    assert "scene_summary" in res
    assert res["confidence"] > 0


def test_image_validation_invalid_extension():
    """Tests image validation with unsupported extension."""
    valid, err = vision_analyzer.validate_image_file("test.exe", b"fake binary data")
    assert valid is False
    assert "Unsupported file type" in err


def test_image_validation_corrupted_data():
    """Tests image validation with corrupted content."""
    valid, err = vision_analyzer.validate_image_file("test.jpg", b"not-a-real-jpeg-header")
    assert valid is False
    assert "Invalid image format" in err


def test_assess_form_data_with_image():
    """Tests /api/assess with multipart form-data including image upload."""
    img = Image.new("RGB", (64, 64), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    files = {"image": ("ROAD-DEBRIS-scaled.jpg", buf, "image/jpeg")}
    data = {
        "vehicle_id": "CAR_A",
        "speed": "60 mph",
        "current_lane": "2",
        "target_lane": "3",
        "direction": "EAST",
        "intended_maneuver": "CHANGE_RIGHT",
        "source_vehicle": "CAR_B",
        "observation": "",
    }

    response = client.post("/api/assess", data=data, files=files)
    assert response.status_code == 200
    res_json = response.json()
    assert "vision_result" in res_json
    assert res_json["risk"] in ("HIGH", "MEDIUM")


def test_video_upload_and_sampling():
    """Tests /api/assess with MP4 video frame sampling."""
    import cv2
    import numpy as np
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        out = cv2.VideoWriter(tf.name, cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
        for _ in range(25):  # 2.5 seconds
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            out.write(frame)
        out.release()
        video_bytes = open(tf.name, "rb").read()
        os.remove(tf.name)

    files = {"image": ("test_road_clip.mp4", io.BytesIO(video_bytes), "video/mp4")}
    data = {
        "vehicle_id": "CAR_A",
        "intended_maneuver": "KEEP_LANE",
        "observation": "",
    }
    response = client.post("/api/assess", data=data, files=files)
    assert response.status_code == 200
    res_json = response.json()
    assert "vision_result" in res_json
    assert res_json["vision_result"].get("total_frames_sampled", 0) >= 1


def test_video_upload_with_video_form_field():
    """Tests /api/assess accepting a file uploaded under the 'video' form field name."""
    import cv2
    import numpy as np
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".mov", delete=False) as tf:
        out = cv2.VideoWriter(tf.name, cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
        for _ in range(15):
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            out.write(frame)
        out.release()
        video_bytes = open(tf.name, "rb").read()
        os.remove(tf.name)

    files = {"video": ("dashcam_debris_lane.mov", io.BytesIO(video_bytes), "video/quicktime")}
    data = {
        "vehicle_id": "CAR_A",
        "intended_maneuver": "KEEP_LANE",
        "observation": "",
    }
    response = client.post("/api/assess", data=data, files=files)
    assert response.status_code == 200
    res_json = response.json()
    assert "vision_result" in res_json
    assert res_json["vision_result"]["media_type"] == "video"
    assert len(res_json["vision_result"]["sampled_timeline"]) >= 1


def test_video_validation():
    """Tests vision analyzer video validation method."""
    valid, err = vision_analyzer.validate_video_file("test.mp4", b"0" * 100)
    assert valid is True
    assert err == ""

    valid, err = vision_analyzer.validate_video_file("test.txt", b"0" * 100)
    assert valid is False
    assert "Unsupported video type" in err

    valid, err = vision_analyzer.validate_video_file("test.mp4", b"tiny")
    assert valid is False
    assert "empty or corrupted" in err


def test_sample_road_hazard_video_static():
    """Tests that the static sample road hazard video exists and can be assessed."""
    import os
    sample_path = "static/sample_road_hazard.mp4"
    assert os.path.exists(sample_path)
    with open(sample_path, "rb") as f:
        content = f.read()

    files = {"video": ("sample_road_hazard.mp4", io.BytesIO(content), "video/mp4")}
    data = {
        "vehicle_id": "CAR_A",
        "speed": "45 mph",
        "intended_maneuver": "KEEP_LANE",
        "observation": "",
    }
    response = client.post("/api/assess", data=data, files=files)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["risk"] in ("HIGH", "MEDIUM")
    assert "vision_result" in res_json
    assert res_json["vision_result"]["total_frames_sampled"] >= 1



@pytest.mark.asyncio
async def test_mock_ibm_api_call():
    """Tests mocking of live IBM Orchestrate API call."""
    from orchestrate import OrchestrateClient
    from unittest.mock import MagicMock

    client_wxo = OrchestrateClient(
        instance_url="https://api.us-south.orchestrate.watsonx.ai.ibm.com/instances/mock-id",
        agent_id="mock-agent-123",
        api_key="mock-key-456",
    )

    mock_chat_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "RISK: HIGH\n"
                        "HAZARD: Hidden pedestrian\n"
                        "WARNING: Pedestrian ahead - wait before turning right.\n"
                        "REASON: Pedestrian may enter road and affects right turn.\n"
                        "SEND TO: CAR_A\n"
                        "CONFIDENCE: HIGH"
                    ),
                }
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_chat_response

    with patch.object(client_wxo.token_manager, "get_access_token", new=AsyncMock(return_value="mock-token-xyz")):
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            res = await client_wxo.assess_hazard(
                vehicle_context={"vehicle_id": "CAR_A", "intended_maneuver": "TURN_RIGHT"},
                road_observation="Pedestrian behind truck",
                source_vehicle="CAR_B",
            )

            assert res["risk"] == "HIGH"
            assert res["hazard"] == "Hidden pedestrian"
            assert res["technical_details"]["connection_status"] == "CONNECTED"



@pytest.mark.asyncio
async def test_mock_ibm_timeout_fallback():
    """Tests IBM timeout error handling gracefully falls back to local reasoning."""
    from orchestrate import OrchestrateClient
    import httpx

    client_wxo = OrchestrateClient(
        instance_url="https://api.us-south.orchestrate.watsonx.ai.ibm.com/instances/mock-id",
        agent_id="mock-agent-123",
        api_key="mock-key-456",
    )

    with patch.object(client_wxo.token_manager, "get_access_token", new=AsyncMock(return_value="mock-token-xyz")):
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
            res = await client_wxo.assess_hazard(
                vehicle_context={"vehicle_id": "CAR_A", "intended_maneuver": "TURN_RIGHT"},
                road_observation="Pedestrian detected moving toward road",
                source_vehicle="CAR_B",
            )
            # Should not raise exception; handles timeout gracefully and returns fallback reasoning
            assert res["risk"] == "HIGH"
            assert "connection_status" in res["technical_details"]

