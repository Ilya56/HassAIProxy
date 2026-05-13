from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.main import create_app


def test_capabilities_returns_configured_allowlists(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    monkeypatch.setenv("READONLY_MODE", "true")
    monkeypatch.setenv("ALLOWED_WRITE_GLOBS", "/config/packages/ai/*.yaml")
    monkeypatch.setenv("ALLOWED_READ_GLOBS", "/config/configuration.yaml,/config/packages/ai/*.yaml")
    monkeypatch.setenv("ALLOWED_HA_SERVICES", "automation.reload,script.reload")
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/capabilities", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 200
    body = response.json()
    assert body["read_only_mode"] is True
    assert body["allowed_write_globs"] == ["/config/packages/ai/*.yaml"]
    assert body["allowed_read_globs"] == ["/config/configuration.yaml", "/config/packages/ai/*.yaml"]
    assert body["allowed_ha_services"] == ["automation.reload", "script.reload"]
    assert body["action_levels"]["apply_changes"] == "C"
    get_settings.cache_clear()

