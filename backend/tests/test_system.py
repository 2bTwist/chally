from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "request_id" in data

def test_version_ok():
    r = client.get("/version")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data and "git_sha" in data
