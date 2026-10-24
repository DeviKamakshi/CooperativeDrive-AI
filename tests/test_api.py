"""API integration tests for ST-06 endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.core.evidence_store import evidence_store

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset evidence store before each test to ensure isolation."""
    evidence_store.reset()
    yield
    evidence_store.reset()


# ---------------------------------------------------------------------------
# Vehicle endpoints
# ---------------------------------------------------------------------------

_VEHICLE_PAYLOAD = {
    "vehicle_id": "CAR_A",
    "position": {"x": 10.0, "y": 20.0},
    "road_segment": "SEG_1",
    "speed_mph": 30.0,
    "acceleration": 0.0,
    "heading_degrees": 90.0,
    "direction": "EAST",
    "lane": 1,
    "intended_maneuver": "KEEP_LANE",
    "source": "SYNTHETIC_SCENARIO",
    "is_simulated": True,
}


def test_vehicles_list_empty(client: TestClient):
    response = client.get("/api/vehicles/")
    assert response.status_code == 200
    assert response.json() == []


def test_vehicle_upsert_and_get(client: TestClient):
    # POST
    post_resp = client.post("/api/vehicles/CAR_A/state", json=_VEHICLE_PAYLOAD)
    assert post_resp.status_code == 201
    assert post_resp.json()["vehicle_id"] == "CAR_A"

    # GET
    get_resp = client.get("/api/vehicles/CAR_A")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["vehicle_id"] == "CAR_A"
    assert body["road_segment"] == "SEG_1"
    assert body["speed_mph"] == 30.0


def test_vehicle_not_found(client: TestClient):
    response = client.get("/api/vehicles/UNKNOWN")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Hazard endpoints
# ---------------------------------------------------------------------------

_HAZARD_PAYLOAD = {
    "hazard_type": "ROAD_DEBRIS",
    "source_vehicle": "CAR_A",
    "road_segment": "SEG_1",
    "position": {"x": 15.0, "y": 20.0},
    "confidence": 0.8,
    "source": "SYNTHETIC_SCENARIO",
}


def test_hazards_list_empty(client: TestClient):
    response = client.get("/api/hazards/")
    assert response.status_code == 200
    assert response.json() == []


def test_add_and_get_hazard(client: TestClient):
    # POST → 201
    post_resp = client.post("/api/hazards/", json=_HAZARD_PAYLOAD)
    assert post_resp.status_code == 201
    hazard_id = post_resp.json()["hazard_id"]
    assert hazard_id.startswith("HZD_")

    # GET by ID
    get_resp = client.get(f"/api/hazards/{hazard_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["hazard_id"] == hazard_id
    assert body["hazard_type"] == "ROAD_DEBRIS"


def test_confirm_hazard(client: TestClient):
    # Create hazard
    post_resp = client.post("/api/hazards/", json=_HAZARD_PAYLOAD)
    assert post_resp.status_code == 201
    hazard_id = post_resp.json()["hazard_id"]

    # Confirm it
    confirm_resp = client.post(
        f"/api/hazards/{hazard_id}/confirm",
        json={"vehicle_id": "CAR_B", "confidence": 0.9},
    )
    assert confirm_resp.status_code == 200
    body = confirm_resp.json()
    assert body["hazard_id"] == hazard_id
    # At least one confirming vehicle recorded
    assert "CAR_B" in body["confirming_vehicles"]


# ---------------------------------------------------------------------------
# Message endpoints
# ---------------------------------------------------------------------------

_MESSAGE_PAYLOAD = {
    "source_vehicle": "CAR_A",
    "message_type": "HAZARD",
    "priority": "NORMAL",
    "road_segment": "SEG_1",
    "position": {"x": 10.0, "y": 20.0},
    "payload": {"hazard_type": "ROAD_DEBRIS"},
}


def test_messages_list_empty(client: TestClient):
    response = client.get("/api/messages/")
    assert response.status_code == 200
    assert response.json() == []


def test_post_message(client: TestClient):
    post_resp = client.post("/api/messages/", json=_MESSAGE_PAYLOAD)
    assert post_resp.status_code == 201
    body = post_resp.json()
    assert body["source_vehicle"] == "CAR_A"
    assert body["message_type"] == "HAZARD"
    msg_id = body["message_id"]

    # Appears in list
    list_resp = client.get("/api/messages/")
    assert list_resp.status_code == 200
    ids = [m["message_id"] for m in list_resp.json()]
    assert msg_id in ids


# ---------------------------------------------------------------------------
# Risk endpoint
# ---------------------------------------------------------------------------


def test_risk_assess_no_hazards(client: TestClient):
    # Register a vehicle first
    client.post("/api/vehicles/CAR_A/state", json=_VEHICLE_PAYLOAD)

    resp = client.post("/api/risk/assess", json={"vehicle_id": "CAR_A"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk"] == "LOW"
    assert body["assessed_vehicle_id"] == "CAR_A"
    assert body["deterministic"] is True


def test_risk_assess_vehicle_not_found(client: TestClient):
    resp = client.post("/api/risk/assess", json={"vehicle_id": "GHOST_CAR"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Scenarios endpoint
# ---------------------------------------------------------------------------


def test_scenarios_list(client: TestClient):
    """GET /api/scenarios should return 200 even when no scenarios are loaded."""
    response = client.get("/api/scenarios/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Health check (existing test preserved)
# ---------------------------------------------------------------------------


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "CooperativeDrive AI"
