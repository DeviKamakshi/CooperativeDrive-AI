from fastapi.testclient import TestClient


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "CooperativeDrive AI"


def test_index(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
