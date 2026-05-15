from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.dependencies import get_ha_client
from homeassistant_proxy.main import create_app
from homeassistant_proxy.services.ha_client import HomeAssistantClientError


class FakeHomeAssistantClient:
    def __init__(self) -> None:
        self.called_services: list[tuple[str, str]] = []

    async def ping(self) -> bool:
        return True

    async def check_config(self) -> dict[str, object]:
        return {"result": "valid", "errors": None}

    async def call_service(
        self,
        *,
        domain: str,
        service: str,
        service_data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.called_services.append((domain, service))
        return {}


class InvalidConfigHomeAssistantClient(FakeHomeAssistantClient):
    async def check_config(self) -> dict[str, object]:
        return {"result": "invalid", "errors": {"automation": "bad trigger"}}


class FailingHomeAssistantClient(FakeHomeAssistantClient):
    async def check_config(self) -> dict[str, object]:
        raise HomeAssistantClientError(
            status_code=503,
            code="ha.token_not_configured",
            message="Home Assistant token is not configured.",
            retryable=False,
        )


def _client(monkeypatch, ha_client: FakeHomeAssistantClient | None = None) -> TestClient:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    monkeypatch.setenv("ALLOWED_HA_SERVICES", "automation.reload,script.reload,homeassistant.reload_all")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: ha_client or FakeHomeAssistantClient()
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-key"}


def test_check_ha_config_returns_validation_result(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post("/ha/config/check", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["checks"][0]["name"] == "ha_config_check"
    assert body["estimated_reload_mode"] == "quick_reload_all"
    get_settings.cache_clear()


def test_check_ha_config_maps_invalid_result(monkeypatch) -> None:
    client = _client(monkeypatch, InvalidConfigHomeAssistantClient())

    response = client.post("/ha/config/check", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["estimated_reload_mode"] == "none"
    assert body["errors"] == ["automation: bad trigger"]
    get_settings.cache_clear()


def test_check_ha_config_maps_client_error(monkeypatch) -> None:
    client = _client(monkeypatch, FailingHomeAssistantClient())

    response = client.post("/ha/config/check", headers=_auth_headers())

    assert response.status_code == 503
    assert response.json()["code"] == "ha.token_not_configured"
    get_settings.cache_clear()


def test_reload_endpoints_require_confirmation_and_call_allowed_services(monkeypatch) -> None:
    ha_client = FakeHomeAssistantClient()
    client = _client(monkeypatch, ha_client)

    unconfirmed_response = client.post(
        "/ha/reload/all",
        headers=_auth_headers(),
        json={"confirmed": False},
    )
    automations_response = client.post(
        "/ha/reload/automations",
        headers=_auth_headers(),
        json={"confirmed": True},
    )
    scripts_response = client.post(
        "/ha/reload/scripts",
        headers=_auth_headers(),
        json={"confirmed": True},
    )
    all_response = client.post(
        "/ha/reload/all",
        headers=_auth_headers(),
        json={"confirmed": True},
    )

    assert unconfirmed_response.status_code == 422
    assert automations_response.json()["action"] == "automations"
    assert scripts_response.json()["action"] == "scripts"
    assert all_response.json()["action"] == "quick_reload_all"
    assert ha_client.called_services == [
        ("automation", "reload"),
        ("script", "reload"),
        ("homeassistant", "reload_all"),
    ]
    get_settings.cache_clear()


def test_reload_rejects_service_outside_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    monkeypatch.setenv("ALLOWED_HA_SERVICES", "automation.reload")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FakeHomeAssistantClient()
    client = TestClient(app)

    response = client.post("/ha/reload/all", headers=_auth_headers(), json={"confirmed": True})

    assert response.status_code == 403
    assert response.json()["code"] == "ha.service_not_allowed"
    get_settings.cache_clear()


def test_restart_endpoint_is_not_implemented(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post("/ha/restart", headers=_auth_headers(), json={"confirmed": True})

    assert response.status_code == 404
    get_settings.cache_clear()
