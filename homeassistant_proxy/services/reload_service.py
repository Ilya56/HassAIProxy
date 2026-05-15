from __future__ import annotations

from typing import Any, Literal

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.models.api_models import ReloadResult, ValidationCheck, ValidationResult
from homeassistant_proxy.services.ha_client import HomeAssistantClient, HomeAssistantClientError


ReloadAction = Literal["automations", "scripts", "quick_reload_all"]


class ReloadService:
    def __init__(self, settings: Settings, ha_client: HomeAssistantClient) -> None:
        self._settings = settings
        self._ha_client = ha_client

    async def check_config(self) -> ValidationResult:
        try:
            payload = await self._ha_client.check_config()
        except HomeAssistantClientError as exc:
            _raise_api_error(exc)

        result = str(payload.get("result", "")).lower()
        raw_errors = payload.get("errors")
        errors = _normalize_errors(raw_errors)
        ok = result == "valid" and not errors
        message = "Home Assistant configuration check passed." if ok else "Home Assistant configuration check failed."

        return ValidationResult(
            ok=ok,
            yaml_valid=None,
            path_allowed=None,
            jinja_parse_status="not_applicable",
            estimated_reload_mode="quick_reload_all" if ok else "none",
            warnings=[],
            errors=errors,
            checks=[
                ValidationCheck(
                    name="ha_config_check",
                    ok=ok,
                    message=message,
                )
            ],
        )

    async def reload(self, action: ReloadAction) -> ReloadResult:
        service_name = _service_name_for_action(action)
        self._require_allowed_service(service_name)
        domain, service = service_name.split(".", 1)

        try:
            await self._ha_client.call_service(domain=domain, service=service)
        except HomeAssistantClientError as exc:
            _raise_api_error(exc)

        return ReloadResult(
            ok=True,
            action=action,
            message=f"Home Assistant service {service_name} was called.",
        )

    async def reload_after_apply(self, validation: ValidationResult) -> ReloadResult:
        if not validation.ok:
            return ReloadResult(ok=False, action="none", message="Reload skipped because validation failed.")

        if validation.estimated_reload_mode == "automations":
            return await self.reload("automations")
        if validation.estimated_reload_mode == "scripts":
            return await self.reload("scripts")
        if validation.estimated_reload_mode == "quick_reload_all":
            return await self.reload("quick_reload_all")
        if validation.estimated_reload_mode == "restart_required":
            return ReloadResult(ok=True, action="restart_required", message="Restart is required and was not performed.")

        return ReloadResult(ok=True, action="none", message="No reload is required.")

    def _require_allowed_service(self, service_name: str) -> None:
        if service_name not in self._settings.allowed_ha_services:
            raise ApiError(
                status_code=403,
                code="ha.service_not_allowed",
                message="The requested Home Assistant service is not allowed by proxy policy.",
                retryable=False,
                details={"service": service_name},
            )


def _service_name_for_action(action: ReloadAction) -> str:
    if action == "automations":
        return "automation.reload"
    if action == "scripts":
        return "script.reload"
    return "homeassistant.reload_all"


def _normalize_errors(raw_errors: Any) -> list[str]:
    if raw_errors is None or raw_errors == "":
        return []
    if isinstance(raw_errors, list):
        return [str(error) for error in raw_errors if str(error).strip()]
    if isinstance(raw_errors, dict):
        return [f"{key}: {value}" for key, value in raw_errors.items()]
    return [str(raw_errors)]


def _raise_api_error(exc: HomeAssistantClientError) -> None:
    raise ApiError(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
    ) from exc
