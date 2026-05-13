from pathlib import Path

from fastapi import APIRouter

from homeassistant_proxy.dependencies import Authenticated, HaClientDep, SettingsDep
from homeassistant_proxy.models.api_models import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, operation_id="getHealth")
async def get_health(_: Authenticated, settings: SettingsDep, ha_client: HaClientDep) -> HealthResponse:
    config_root = Path(settings.config_root)
    ha_reachable = await ha_client.ping()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        ha_reachable=ha_reachable,
        file_storage_ok=config_root.exists(),
    )
