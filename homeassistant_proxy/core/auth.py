import secrets

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from homeassistant_proxy.config import Settings, get_settings
from homeassistant_proxy.core.errors import ApiError

bearer_scheme = HTTPBearer(auto_error=False)


def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=401,
            code="auth.missing_bearer_token",
            message="Bearer API key is required.",
            retryable=False,
        )

    if not secrets.compare_digest(credentials.credentials, settings.app_api_key):
        raise ApiError(
            status_code=401,
            code="auth.invalid_api_key",
            message="Bearer API key is invalid.",
            retryable=False,
        )

