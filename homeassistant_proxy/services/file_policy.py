from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError

CONFIG_PREFIX = "/config"


@dataclass(frozen=True)
class ResolvedFilePath:
    api_path: str
    relative_path: str


class FilePathPolicy:
    def __init__(self, settings: Settings) -> None:
        self._allowed_read_globs = settings.allowed_read_globs
        self._allowed_write_globs = settings.allowed_write_globs

    @property
    def allowed_read_globs(self) -> list[str]:
        return self._allowed_read_globs

    def resolve_read_path(self, path: str) -> ResolvedFilePath:
        api_path = self.normalize_api_path(path)
        self.reject_forbidden(api_path)
        if not self.matches_read(api_path):
            raise ApiError(
                status_code=403,
                code="files.path_not_allowed",
                message="The requested path is not in the configured read allowlist.",
                retryable=False,
                details={"path": api_path},
            )

        return self._to_resolved_path(api_path)

    def resolve_write_path(self, path: str) -> ResolvedFilePath:
        api_path = self.normalize_api_path(path)
        self.reject_forbidden(api_path)
        if not self.matches_write(api_path):
            raise ApiError(
                status_code=403,
                code="files.path_not_writable",
                message="The requested path is not in the configured write allowlist.",
                retryable=False,
                details={"path": api_path},
            )

        return self._to_resolved_path(api_path)

    def resolve_prefix(self, path: str) -> str:
        api_path = self.normalize_prefix(path)
        if api_path is None:
            return ""
        return api_path.removeprefix(f"{CONFIG_PREFIX}/").rstrip("/")

    def normalize_api_path(self, path: str) -> str:
        normalized = PurePosixPath(path.replace("\\", "/")).as_posix()
        if normalized == CONFIG_PREFIX:
            return normalized
        if not normalized.startswith(f"{CONFIG_PREFIX}/"):
            raise ApiError(
                status_code=403,
                code="files.path_not_allowed",
                message="File paths must use Home Assistant-style /config paths.",
                retryable=False,
                details={"path": path},
            )
        if ".." in PurePosixPath(normalized).parts:
            raise self._forbidden_path_escape()
        return normalized

    def normalize_prefix(self, path_prefix: str | None) -> str | None:
        if path_prefix is None or path_prefix == "":
            return None
        normalized = self.normalize_api_path(path_prefix)
        return normalized if normalized.endswith("/") else f"{normalized}/"

    def relative_to_api_path(self, relative_path: str) -> str:
        return f"{CONFIG_PREFIX}/{PurePosixPath(relative_path).as_posix()}"

    def reject_forbidden(self, api_path: str) -> None:
        path = PurePosixPath(api_path)
        parts = path.parts
        if path.name == "secrets.yaml" or any(part.startswith(".") for part in parts if part not in {"/"}):
            raise self._forbidden_path()
        if "/.storage/" in api_path or "/backups/" in api_path or "/ssl/" in api_path:
            raise self._forbidden_path()
        if path.suffix.lower() == ".db":
            raise self._forbidden_path()

    def matches_read(self, api_path: str) -> bool:
        return self._matches_any(api_path, self._allowed_read_globs)

    def matches_write(self, api_path: str) -> bool:
        return self._matches_any(api_path, self._allowed_write_globs)

    def _to_resolved_path(self, api_path: str) -> ResolvedFilePath:
        relative_path = api_path.removeprefix(f"{CONFIG_PREFIX}/")
        return ResolvedFilePath(api_path=api_path, relative_path=relative_path)

    def _matches_any(self, api_path: str, globs: list[str]) -> bool:
        return any(fnmatchcase(api_path, self.normalize_api_path(pattern)) for pattern in globs)

    def _forbidden_path(self) -> ApiError:
        return ApiError(
            status_code=403,
            code="files.forbidden_path",
            message="The requested path is forbidden by proxy policy.",
            retryable=False,
        )

    def _forbidden_path_escape(self) -> ApiError:
        return ApiError(
            status_code=403,
            code="files.path_escape",
            message="The requested path escapes the configured Home Assistant config root.",
            retryable=False,
        )
