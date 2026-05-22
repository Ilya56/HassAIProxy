from typing import Any

import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient

from homeassistant_proxy.config import Settings, get_settings
from homeassistant_proxy.core.errors import ApiError, install_error_handlers
from homeassistant_proxy.core.sentry import configure_sentry, redact_sensitive_data
from homeassistant_proxy.main import create_app


def test_configure_sentry_skips_init_without_dsn(monkeypatch) -> None:
    called = False

    def fake_init(**kwargs: Any) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(sentry_sdk, "init", fake_init)

    configure_sentry(Settings())

    assert called is False


def test_configure_sentry_uses_safe_defaults(monkeypatch) -> None:
    init_kwargs: dict[str, Any] = {}

    def fake_init(**kwargs: Any) -> None:
        init_kwargs.update(kwargs)

    monkeypatch.setattr(sentry_sdk, "init", fake_init)

    configure_sentry(Settings(app_env="prod", sentry_dsn="https://example@sentry.invalid/1"))

    assert init_kwargs["dsn"] == "https://example@sentry.invalid/1"
    assert init_kwargs["environment"] == "prod"
    assert init_kwargs["traces_sample_rate"] == 0.1
    assert init_kwargs["send_default_pii"] is False
    assert init_kwargs["include_local_variables"] is False
    assert init_kwargs["max_request_body_size"] == "never"


def test_redact_sensitive_data_recurses_through_mappings() -> None:
    redacted = redact_sensitive_data(
        {
            "Authorization": "Bearer token",
            "nested": {
                "ha_token": "secret",
                "safe": "value",
            },
            "items": [{"SFTP_PRIVATE_KEY": "secret-key"}],
            "headers": [("Authorization", "Bearer token")],
        }
    )

    assert redacted == {
        "Authorization": "[redacted]",
        "nested": {
            "ha_token": "[redacted]",
            "safe": "value",
        },
        "items": [{"SFTP_PRIVATE_KEY": "[redacted]"}],
        "headers": [("Authorization", "[redacted]")],
    }


def test_api_error_handler_captures_5xx_api_errors(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_capture_api_error(exc: BaseException, **kwargs: Any) -> None:
        captured["exc"] = exc
        captured.update(kwargs)

    monkeypatch.setattr("homeassistant_proxy.core.errors.capture_api_error", fake_capture_api_error)
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise ApiError(
            status_code=502,
            code="files.remote_transport_error",
            message="Remote file transport failed.",
            retryable=True,
            details={"operation": "write_text"},
        )

    response = TestClient(app).get("/boom")

    assert response.status_code == 502
    assert captured["path"] == "/boom"
    assert captured["method"] == "GET"
    assert captured["status_code"] == 502
    assert captured["code"] == "files.remote_transport_error"
    assert captured["details"] == {"operation": "write_text"}


def test_api_error_handler_does_not_capture_4xx_api_errors(monkeypatch) -> None:
    captured = False

    def fake_capture_api_error(exc: BaseException, **kwargs: Any) -> None:
        nonlocal captured
        captured = True

    monkeypatch.setattr("homeassistant_proxy.core.errors.capture_api_error", fake_capture_api_error)
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/policy-denied")
    async def policy_denied() -> None:
        raise ApiError(
            status_code=403,
            code="files.forbidden_path",
            message="The requested path is not allowed.",
            retryable=False,
        )

    response = TestClient(app).get("/policy-denied")

    assert response.status_code == 403
    assert captured is False


def test_sentry_debug_route_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SENTRY_DEBUG_ROUTE_ENABLED", raising=False)
    get_settings.cache_clear()

    client = TestClient(create_app())

    assert client.get("/sentry-debug").status_code == 404
    get_settings.cache_clear()


def test_sentry_debug_route_can_be_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_DEBUG_ROUTE_ENABLED", "true")
    get_settings.cache_clear()

    client = TestClient(create_app(), raise_server_exceptions=False)

    assert client.get("/sentry-debug").status_code == 500
    get_settings.cache_clear()
