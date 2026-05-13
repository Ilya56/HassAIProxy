from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.main import create_app


def test_health_requires_bearer_token() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.missing_bearer_token"


def test_health_returns_status_with_valid_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/health", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["ha_reachable"] is False
    assert isinstance(body["file_storage_ok"], bool)
    get_settings.cache_clear()
