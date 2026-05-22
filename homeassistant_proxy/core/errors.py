import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from homeassistant_proxy.core.sentry import capture_api_error

logger = logging.getLogger(__name__)


class ApiError(Exception):
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


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        if exc.status_code >= 500:
            capture_api_error(
                exc,
                path=request.url.path,
                method=request.method,
                status_code=exc.status_code,
                code=exc.code,
                details=exc.details,
            )
        logger.warning(
            "api_error path=%s method=%s status_code=%s code=%s retryable=%s details=%s",
            request.url.path,
            request.method,
            exc.status_code,
            exc.code,
            exc.retryable,
            exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "retryable": exc.retryable,
            },
        )
