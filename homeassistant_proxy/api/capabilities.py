from fastapi import APIRouter

from homeassistant_proxy.dependencies import Authenticated, SettingsDep
from homeassistant_proxy.models.api_models import CapabilitiesResponse

router = APIRouter(tags=["Capabilities"])


@router.get("/capabilities", response_model=CapabilitiesResponse, operation_id="getCapabilities")
def get_capabilities(_: Authenticated, settings: SettingsDep) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        read_only_mode=settings.readonly_mode,
        allowed_read_globs=settings.allowed_read_globs,
        allowed_write_globs=settings.allowed_write_globs,
        allowed_ha_services=settings.allowed_ha_services,
        action_levels={
            "read": "A",
            "prepare_changes": "B",
            "apply_changes": "C",
        },
    )

