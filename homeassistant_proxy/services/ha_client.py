from typing import Any

import httpx

from homeassistant_proxy.config import Settings


class HomeAssistantClientError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


class HomeAssistantClient:
    def __init__(self, client: httpx.AsyncClient, has_token: bool) -> None:
        self._client = client
        self._has_token = has_token

    @classmethod
    def from_settings(cls, settings: Settings) -> "HomeAssistantClient":
        headers = {}
        if settings.ha_token:
            headers["Authorization"] = f"Bearer {settings.ha_token}"

        client = httpx.AsyncClient(
            base_url=settings.ha_base_url.rstrip("/"),
            headers=headers,
            timeout=settings.request_timeout_seconds,
        )
        return cls(client=client, has_token=bool(settings.ha_token))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ping(self) -> bool:
        if not self._has_token:
            return False

        try:
            response = await self._client.get("/api/")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_config(self) -> dict[str, Any]:
        if not self._has_token:
            raise HomeAssistantClientError(
                status_code=503,
                code="ha.token_not_configured",
                message="Home Assistant token is not configured.",
                retryable=False,
            )

        try:
            response = await self._client.get("/api/config")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HomeAssistantClientError(
                status_code=502,
                code="ha.request_failed",
                message="Home Assistant API returned an error.",
                retryable=exc.response.status_code >= 500,
                details={"ha_status_code": exc.response.status_code},
            ) from exc
        except httpx.TimeoutException as exc:
            raise HomeAssistantClientError(
                status_code=504,
                code="ha.request_timeout",
                message="Home Assistant API request timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise HomeAssistantClientError(
                status_code=502,
                code="ha.request_failed",
                message="Home Assistant API request failed.",
                retryable=True,
            ) from exc

        data = response.json()
        if not isinstance(data, dict):
            raise HomeAssistantClientError(
                status_code=502,
                code="ha.invalid_response",
                message="Home Assistant API returned an unexpected response.",
                retryable=False,
            )

        return data
