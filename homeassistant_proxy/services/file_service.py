from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from hashlib import sha256
from pathlib import PurePosixPath

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.models.api_models import FileContent, FileInfo
from homeassistant_proxy.services.file_backends import FileBackend, build_file_backend

CONFIG_PREFIX = "/config"


@dataclass(frozen=True)
class ResolvedFilePath:
    api_path: str
    relative_path: str


class FileService:
    def __init__(self, settings: Settings, backend: FileBackend | None = None) -> None:
        self._allowed_read_globs = settings.allowed_read_globs
        self._allowed_write_globs = settings.allowed_write_globs
        self._max_file_size_bytes = settings.max_file_size_kb * 1024
        self._backend = backend or build_file_backend(settings)

    async def list_files(self, path_prefix: str | None = None) -> list[FileInfo]:
        prefix = self._normalize_prefix(path_prefix)
        files: dict[str, FileInfo] = {}

        for allowed_glob in self._allowed_read_globs:
            for api_path in await self._iter_matching_api_paths(allowed_glob):
                if prefix is not None and not api_path.startswith(prefix):
                    continue
                try:
                    resolved = self._resolve_allowed_path(api_path)
                    files[api_path] = await self.get_metadata_for_resolved(resolved)
                except ApiError:
                    continue

        return [files[path] for path in sorted(files)]

    async def read_file(self, path: str) -> FileContent:
        resolved = self._resolve_allowed_path(path)
        file_stat = await self._backend.stat(resolved.relative_path)

        if file_stat.size_bytes > self._max_file_size_bytes:
            raise ApiError(
                status_code=413,
                code="files.file_too_large",
                message="The requested file exceeds the configured maximum file size.",
                retryable=False,
                details={"path": resolved.api_path, "max_file_size_bytes": self._max_file_size_bytes},
            )

        content = await self._backend.read_text(resolved.relative_path)
        return FileContent(
            path=resolved.api_path,
            content=content,
            content_hash=self._hash_content(content),
        )

    async def get_metadata(self, path: str) -> FileInfo:
        resolved = self._resolve_allowed_path(path)
        return await self.get_metadata_for_resolved(resolved)

    async def get_metadata_for_resolved(self, resolved: ResolvedFilePath) -> FileInfo:
        file_stat = await self._backend.stat(resolved.relative_path)
        content = await self._backend.read_text(resolved.relative_path)
        return FileInfo(
            path=resolved.api_path,
            writable=self._matches_any(resolved.api_path, self._allowed_write_globs),
            size_bytes=file_stat.size_bytes,
            content_hash=self._hash_content(content),
            modified_at=file_stat.modified_at.isoformat(),
        )

    def _resolve_allowed_path(self, path: str) -> ResolvedFilePath:
        api_path = self._normalize_api_path(path)
        self._reject_forbidden(api_path)
        if not self._matches_any(api_path, self._allowed_read_globs):
            raise ApiError(
                status_code=403,
                code="files.path_not_allowed",
                message="The requested path is not in the configured read allowlist.",
                retryable=False,
                details={"path": api_path},
            )

        relative_path = api_path.removeprefix(f"{CONFIG_PREFIX}/")
        return ResolvedFilePath(api_path=api_path, relative_path=relative_path)

    async def _iter_matching_api_paths(self, allowed_glob: str) -> list[str]:
        normalized_glob = self._normalize_api_path(allowed_glob)
        if not any(token in normalized_glob for token in ("*", "?", "[")):
            return [normalized_glob]

        base = normalized_glob.split("*", 1)[0].rsplit("/", 1)[0]
        try:
            base_resolved = self._resolve_prefix(base)
        except ApiError:
            return []

        matches: list[str] = []
        for relative_path in await self._backend.list_files(base_resolved):
            api_path = self._relative_to_api_path(relative_path)
            if fnmatchcase(api_path, normalized_glob):
                matches.append(api_path)
        return matches

    def _resolve_prefix(self, path: str) -> str:
        api_path = self._normalize_prefix(path)
        if api_path is None:
            return ""
        return api_path.removeprefix(f"{CONFIG_PREFIX}/").rstrip("/")

    def _relative_to_api_path(self, relative_path: str) -> str:
        return f"{CONFIG_PREFIX}/{PurePosixPath(relative_path).as_posix()}"

    def _normalize_api_path(self, path: str) -> str:
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

    def _normalize_prefix(self, path_prefix: str | None) -> str | None:
        if path_prefix is None or path_prefix == "":
            return None
        normalized = self._normalize_api_path(path_prefix)
        return normalized if normalized.endswith("/") else f"{normalized}/"

    def _reject_forbidden(self, api_path: str) -> None:
        path = PurePosixPath(api_path)
        parts = path.parts
        if path.name == "secrets.yaml" or any(part.startswith(".") for part in parts if part not in {"/"}):
            raise self._forbidden_path()
        if "/.storage/" in api_path or "/backups/" in api_path or "/ssl/" in api_path:
            raise self._forbidden_path()
        if path.suffix.lower() == ".db":
            raise self._forbidden_path()

    def _matches_any(self, api_path: str, globs: list[str]) -> bool:
        return any(fnmatchcase(api_path, self._normalize_api_path(pattern)) for pattern in globs)

    def _hash_content(self, content: str) -> str:
        return sha256(content.encode("utf-8")).hexdigest()

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

    def _not_found(self) -> ApiError:
        return ApiError(
            status_code=404,
            code="files.not_found",
            message="The requested file was not found.",
            retryable=False,
        )
