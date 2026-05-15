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

    async def get_states(self) -> list[dict[str, Any]]:
        data = await self._get_json("/api/states")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise HomeAssistantClientError(
                status_code=502,
                code="ha.invalid_response",
                message="Home Assistant API returned an unexpected response.",
                retryable=False,
            )
        return data

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        data = await self._get_json(f"/api/states/{entity_id}", not_found_code="ha.entity_not_found")
        if not isinstance(data, dict):
            raise HomeAssistantClientError(
                status_code=502,
                code="ha.invalid_response",
                message="Home Assistant API returned an unexpected response.",
                retryable=False,
            )
        return data

    async def check_config(self) -> dict[str, Any]:
        data = await self._post_json("/api/config/core/check_config")
        if not isinstance(data, dict):
            raise HomeAssistantClientError(
                status_code=502,
                code="ha.invalid_response",
                message="Home Assistant API returned an unexpected response.",
                retryable=False,
            )
        return data

    async def call_service(
        self,
        *,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        return await self._post_json(f"/api/services/{domain}/{service}", json=service_data or {}, timeout=timeout)

    async def _get_json(self, path: str, *, not_found_code: str = "ha.not_found") -> Any:
        if not self._has_token:
            raise HomeAssistantClientError(
                status_code=503,
                code="ha.token_not_configured",
                message="Home Assistant token is not configured.",
                retryable=False,
            )

        try:
            response = await self._client.get(path)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise HomeAssistantClientError(
                    status_code=404,
                    code=not_found_code,
                    message="Home Assistant resource was not found.",
                    retryable=False,
                ) from exc
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

        return response.json()

    async def _post_json(self, path: str, *, json: dict[str, Any] | None = None, timeout: float | None = None) -> Any:
        if not self._has_token:
            raise HomeAssistantClientError(
                status_code=503,
                code="ha.token_not_configured",
                message="Home Assistant token is not configured.",
                retryable=False,
            )

        try:
            response = await self._client.post(path, json=json, timeout=timeout)
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

        if response.content == b"":
            return {}
        return response.json()
