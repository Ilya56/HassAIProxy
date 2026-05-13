from fastapi import APIRouter

from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.dependencies import Authenticated, HaClientDep
from homeassistant_proxy.models.api_models import (
    AutomationListResponse,
    EntityListResponse,
    EntityState,
    EntitySummary,
    HaConfigResponse,
    ScriptListResponse,
)
from homeassistant_proxy.services.ha_client import HomeAssistantClientError

router = APIRouter(prefix="/ha", tags=["Home Assistant Read"])


@router.get("/config", response_model=HaConfigResponse, operation_id="getHaConfig")
async def get_ha_config(_: Authenticated, ha_client: HaClientDep) -> HaConfigResponse:
    try:
        config = await ha_client.get_config()
    except HomeAssistantClientError as exc:
        raise ApiError(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
        ) from exc

    return HaConfigResponse(
        location_name=config.get("location_name", ""),
        time_zone=config.get("time_zone"),
        unit_system=config.get("unit_system"),
        version=config.get("version"),
    )


@router.get("/entities", response_model=EntityListResponse, operation_id="listEntities")
async def list_entities(
    _: Authenticated,
    ha_client: HaClientDep,
    query: str | None = None,
    domain: str | None = None,
    area_id: str | None = None,
    device_class: str | None = None,
) -> EntityListResponse:
    states = await _get_states_or_raise(ha_client)
    entities = [
        _to_entity_summary(state)
        for state in states
        if _matches_filters(state, query=query, domain=domain, area_id=area_id, device_class=device_class)
    ]
    return EntityListResponse(entities=entities)


@router.get("/entities/{entity_id}", response_model=EntityState, operation_id="getEntityState")
async def get_entity_state(_: Authenticated, ha_client: HaClientDep, entity_id: str) -> EntityState:
    try:
        state = await ha_client.get_state(entity_id)
    except HomeAssistantClientError as exc:
        _raise_api_error(exc)

    return _to_entity_state(state)


@router.get("/automations", response_model=AutomationListResponse, operation_id="listAutomations")
async def list_automations(
    _: Authenticated,
    ha_client: HaClientDep,
    query: str | None = None,
) -> AutomationListResponse:
    states = await _get_states_or_raise(ha_client)
    automations = [
        _to_entity_summary(state)
        for state in states
        if _matches_filters(state, query=query, domain="automation", area_id=None, device_class=None)
    ]
    return AutomationListResponse(automations=automations)


@router.get("/scripts", response_model=ScriptListResponse, operation_id="listScripts")
async def list_scripts(
    _: Authenticated,
    ha_client: HaClientDep,
    query: str | None = None,
) -> ScriptListResponse:
    states = await _get_states_or_raise(ha_client)
    scripts = [
        _to_entity_summary(state)
        for state in states
        if _matches_filters(state, query=query, domain="script", area_id=None, device_class=None)
    ]
    return ScriptListResponse(scripts=scripts)


async def _get_states_or_raise(ha_client: object) -> list[dict[str, object]]:
    try:
        return await ha_client.get_states()
    except HomeAssistantClientError as exc:
        _raise_api_error(exc)


def _raise_api_error(exc: HomeAssistantClientError) -> None:
    raise ApiError(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
    ) from exc


def _to_entity_summary(state: dict[str, object]) -> EntitySummary:
    entity_id = str(state.get("entity_id", ""))
    attributes = _attributes(state)
    return EntitySummary(
        entity_id=entity_id,
        domain=_domain(entity_id),
        friendly_name=_optional_string(attributes.get("friendly_name")),
        state=_optional_string(state.get("state")),
    )


def _to_entity_state(state: dict[str, object]) -> EntityState:
    return EntityState(
        entity_id=str(state.get("entity_id", "")),
        state=str(state.get("state", "")),
        attributes=_attributes(state),
        last_changed=str(state.get("last_changed", "")),
        last_updated=str(state.get("last_updated", "")),
    )


def _matches_filters(
    state: dict[str, object],
    *,
    query: str | None,
    domain: str | None,
    area_id: str | None,
    device_class: str | None,
) -> bool:
    entity_id = str(state.get("entity_id", ""))
    attributes = _attributes(state)

    if domain is not None and _domain(entity_id) != domain:
        return False
    if area_id is not None and attributes.get("area_id") != area_id:
        return False
    if device_class is not None and attributes.get("device_class") != device_class:
        return False
    if query is not None and query.strip():
        needle = query.casefold()
        haystacks = [
            entity_id,
            _optional_string(attributes.get("friendly_name")) or "",
            _optional_string(state.get("state")) or "",
        ]
        return any(needle in haystack.casefold() for haystack in haystacks)

    return True


def _attributes(state: dict[str, object]) -> dict[str, object]:
    attributes = state.get("attributes", {})
    return attributes if isinstance(attributes, dict) else {}


def _domain(entity_id: str) -> str | None:
    if "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
