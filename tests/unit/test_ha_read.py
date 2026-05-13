from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.dependencies import get_ha_client
from homeassistant_proxy.main import create_app
from homeassistant_proxy.services.ha_client import HomeAssistantClientError


class FakeHomeAssistantClient:
    states = [
        {
            "entity_id": "sensor.living_room_co2",
            "state": "812",
            "attributes": {
                "friendly_name": "Living Room CO2",
                "device_class": "carbon_dioxide",
                "area_id": "living_room",
            },
            "last_changed": "2026-05-13T18:00:00+00:00",
            "last_updated": "2026-05-13T18:01:00+00:00",
        },
        {
            "entity_id": "automation.ventilation_boost",
            "state": "on",
            "attributes": {"friendly_name": "Ventilation Boost"},
            "last_changed": "2026-05-13T18:02:00+00:00",
            "last_updated": "2026-05-13T18:03:00+00:00",
        },
        {
            "entity_id": "script.goodnight",
            "state": "off",
            "attributes": {"friendly_name": "Goodnight"},
            "last_changed": "2026-05-13T18:04:00+00:00",
            "last_updated": "2026-05-13T18:05:00+00:00",
        },
    ]

    async def ping(self) -> bool:
        return True

    async def get_config(self) -> dict[str, object]:
        return {
            "location_name": "Home",
            "time_zone": "Europe/Kiev",
            "unit_system": {"temperature": "C"},
            "version": "2026.5.0",
        }

    async def get_states(self) -> list[dict[str, object]]:
        return self.states

    async def get_state(self, entity_id: str) -> dict[str, object]:
        for state in self.states:
            if state["entity_id"] == entity_id:
                return state
        raise HomeAssistantClientError(
            status_code=404,
            code="ha.entity_not_found",
            message="Home Assistant resource was not found.",
            retryable=False,
        )


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

    async def get_states(self) -> list[dict[str, object]]:
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


def test_list_entities_filters_by_query_domain_area_and_device_class(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FakeHomeAssistantClient()
    client = TestClient(app)

    response = client.get(
        "/ha/entities",
        params={
            "query": "living",
            "domain": "sensor",
            "area_id": "living_room",
            "device_class": "carbon_dioxide",
        },
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "entities": [
            {
                "entity_id": "sensor.living_room_co2",
                "domain": "sensor",
                "friendly_name": "Living Room CO2",
                "state": "812",
            }
        ]
    }
    get_settings.cache_clear()


def test_get_entity_state_returns_full_state(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FakeHomeAssistantClient()
    client = TestClient(app)

    response = client.get(
        "/ha/entities/sensor.living_room_co2",
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "entity_id": "sensor.living_room_co2",
        "state": "812",
        "attributes": {
            "friendly_name": "Living Room CO2",
            "device_class": "carbon_dioxide",
            "area_id": "living_room",
        },
        "last_changed": "2026-05-13T18:00:00+00:00",
        "last_updated": "2026-05-13T18:01:00+00:00",
    }
    get_settings.cache_clear()


def test_get_entity_state_maps_not_found(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FakeHomeAssistantClient()
    client = TestClient(app)

    response = client.get(
        "/ha/entities/sensor.missing",
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "ha.entity_not_found"
    get_settings.cache_clear()


def test_list_automations_filters_automation_domain(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FakeHomeAssistantClient()
    client = TestClient(app)

    response = client.get(
        "/ha/automations",
        params={"query": "boost"},
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "automations": [
            {
                "entity_id": "automation.ventilation_boost",
                "domain": "automation",
                "friendly_name": "Ventilation Boost",
                "state": "on",
            }
        ]
    }
    get_settings.cache_clear()


def test_list_scripts_filters_script_domain(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FakeHomeAssistantClient()
    client = TestClient(app)

    response = client.get(
        "/ha/scripts",
        params={"query": "good"},
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "scripts": [
            {
                "entity_id": "script.goodnight",
                "domain": "script",
                "friendly_name": "Goodnight",
                "state": "off",
            }
        ]
    }
    get_settings.cache_clear()


def test_list_entities_maps_client_error(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_ha_client] = lambda: FailingHomeAssistantClient()
    client = TestClient(app)

    response = client.get("/ha/entities", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 503
    assert response.json()["code"] == "ha.token_not_configured"
    get_settings.cache_clear()
