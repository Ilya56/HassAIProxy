from fastapi import APIRouter

from homeassistant_proxy.dependencies import Authenticated, ReloadServiceDep
from homeassistant_proxy.models.api_models import ConfirmedActionRequest, ReloadResult, ValidationResult

router = APIRouter(prefix="/ha", tags=["Config Operations"])


@router.post("/config/check", response_model=ValidationResult, operation_id="checkHaConfig")
async def check_ha_config(_: Authenticated, reload_service: ReloadServiceDep) -> ValidationResult:
    return await reload_service.check_config()


@router.post("/reload/automations", response_model=ReloadResult, operation_id="reloadAutomations")
async def reload_automations(
    _: Authenticated,
    reload_service: ReloadServiceDep,
    request: ConfirmedActionRequest,
) -> ReloadResult:
    return await reload_service.reload("automations")


@router.post("/reload/scripts", response_model=ReloadResult, operation_id="reloadScripts")
async def reload_scripts(
    _: Authenticated,
    reload_service: ReloadServiceDep,
    request: ConfirmedActionRequest,
) -> ReloadResult:
    return await reload_service.reload("scripts")


@router.post("/reload/all", response_model=ReloadResult, operation_id="quickReloadAll")
async def quick_reload_all(
    _: Authenticated,
    reload_service: ReloadServiceDep,
    request: ConfirmedActionRequest,
) -> ReloadResult:
    return await reload_service.reload("quick_reload_all")
