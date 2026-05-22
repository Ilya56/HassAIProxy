from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import sentry_sdk

from homeassistant_proxy.config import Settings, get_settings

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "token",
    "secret",
    "password",
    "passphrase",
    "private_key",
    "api_key",
    "dsn",
)
_REDACTED = "[redacted]"


def configure_sentry(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.sentry_release or None,
        traces_sample_rate=_traces_sample_rate(settings),
        send_default_pii=settings.sentry_send_default_pii,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=_before_send,
        before_send_transaction=_before_send_transaction,
    )


def capture_api_error(
    exc: BaseException,
    *,
    path: str,
    method: str,
    status_code: int,
    code: str,
    details: Mapping[str, Any],
) -> None:
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("api.path", path)
        scope.set_tag("api.method", method)
        scope.set_tag("api.status_code", status_code)
        scope.set_tag("api.error_code", code)
        scope.set_context(
            "api_error",
            {
                "path": path,
                "method": method,
                "status_code": status_code,
                "code": code,
                "details": redact_sensitive_data(details),
            },
        )
        sentry_sdk.capture_exception(exc)


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _REDACTED if _is_sensitive_key(str(key)) else redact_sensitive_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        if len(value) == 2 and isinstance(value[0], str) and _is_sensitive_key(value[0]):
            return (value[0], _REDACTED)
        return tuple(redact_sensitive_data(item) for item in value)
    return value


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    return _sanitize_event(event)


def _before_send_transaction(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    return _sanitize_event(event)


def _sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        request["headers"] = redact_sensitive_data(request.get("headers", {}))
        request["env"] = redact_sensitive_data(request.get("env", {}))

    event["extra"] = redact_sensitive_data(event.get("extra", {}))
    event["contexts"] = redact_sensitive_data(event.get("contexts", {}))
    return event


def _traces_sample_rate(settings: Settings) -> float:
    if settings.sentry_traces_sample_rate is not None:
        return settings.sentry_traces_sample_rate
    if settings.app_env == "prod":
        return 0.1
    return 0.0


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)
