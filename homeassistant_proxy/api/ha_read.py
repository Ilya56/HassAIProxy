from fastapi import APIRouter

from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.dependencies import Authenticated, HaClientDep
from homeassistant_proxy.models.api_models import HaConfigResponse
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
