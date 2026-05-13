from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.dependencies import get_ha_client
from homeassistant_proxy.main import create_app
from homeassistant_proxy.services.ha_client import HomeAssistantClientError


class FakeHomeAssistantClient:
    async def ping(self) -> bool:
        return True

    async def get_config(self) -> dict[str, object]:
        return {
            "location_name": "Home",
            "time_zone": "Europe/Kiev",
            "unit_system": {"temperature": "C"},
            "version": "2026.5.0",
        }


class FailingHomeAssistantClient:
    async def ping(self) -> bool:
        return False

    async def get_config(self) -> dict[str, object]:
        raise HomeAssistantClientError(
            status_code=503,
            code="ha.token_not_configured",
            message="Home Assistant token is not configured.",
            retryable=False,
        )


def test_get_ha_config_returns_config(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FakeHomeAssistantClient()
    client = TestClient(app)

    response = client.get("/ha/config", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 200
    assert response.json() == {
        "location_name": "Home",
        "time_zone": "Europe/Kiev",
        "unit_system": {"temperature": "C"},
        "version": "2026.5.0",
    }
    get_settings.cache_clear()


def test_get_ha_config_maps_client_error(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FailingHomeAssistantClient()
    client = TestClient(app)

    response = client.get("/ha/config", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 503
    assert response.json()["code"] == "ha.token_not_configured"
    get_settings.cache_clear()
