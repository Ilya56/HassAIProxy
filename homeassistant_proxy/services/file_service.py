from __future__ import annotations

from hashlib import sha256

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.models.api_models import FileContent, FileInfo, FileSearchMatch
from homeassistant_proxy.services.file_backends import FileBackend, build_file_backend
from homeassistant_proxy.services.file_policy import FilePathPolicy, ResolvedFilePath

MAX_SEARCH_MATCHES = 100


class FileService:
    def __init__(self, settings: Settings, backend: FileBackend | None = None) -> None:
        self._path_policy = FilePathPolicy(settings)
        self._max_file_size_bytes = settings.max_file_size_kb * 1024
        self._backend = backend or build_file_backend(settings)

    async def list_files(self, path_prefix: str | None = None) -> list[FileInfo]:
        prefix = self._path_policy.normalize_prefix(path_prefix)
        files: dict[str, FileInfo] = {}

        for allowed_glob in self._path_policy.allowed_read_globs:
            for api_path in await self._iter_matching_api_paths(allowed_glob):
                if prefix is not None and not api_path.startswith(prefix):
                    continue
                try:
                    resolved = self._path_policy.resolve_read_path(api_path)
                    files[api_path] = await self.get_metadata_for_resolved(resolved)
                except ApiError:
                    continue

        return [files[path] for path in sorted(files)]

    async def read_file(self, path: str) -> FileContent:
        resolved = self._path_policy.resolve_read_path(path)
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
        resolved = self._path_policy.resolve_read_path(path)
        return await self.get_metadata_for_resolved(resolved)

    async def read_writable_file(self, path: str) -> FileContent:
        resolved = self._path_policy.resolve_write_path(path)
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

    async def writable_file_exists(self, path: str) -> bool:
        resolved = self._path_policy.resolve_write_path(path)
        try:
            await self._backend.stat(resolved.relative_path)
        except ApiError as exc:
            if exc.code == "files.not_found":
                return False
            raise
        return True

    async def write_writable_file(self, path: str, content: str) -> FileContent:
        resolved = self._path_policy.resolve_write_path(path)
        await self._backend.write_text(resolved.relative_path, content)
        return FileContent(
            path=resolved.api_path,
            content=content,
            content_hash=self._hash_content(content),
        )

    async def delete_writable_file(self, path: str) -> None:
        resolved = self._path_policy.resolve_write_path(path)
        await self._backend.delete_file(resolved.relative_path)

    def normalize_writable_path(self, path: str) -> str:
        return self._path_policy.resolve_write_path(path).api_path

    def hash_content(self, content: str) -> str:
        return self._hash_content(content)

    async def get_metadata_for_resolved(self, resolved: ResolvedFilePath) -> FileInfo:
        file_stat = await self._backend.stat(resolved.relative_path)
        content = await self._backend.read_text(resolved.relative_path)
        return FileInfo(
            path=resolved.api_path,
            writable=self._path_policy.matches_write(resolved.api_path),
            size_bytes=file_stat.size_bytes,
            content_hash=self._hash_content(content),
            modified_at=file_stat.modified_at.isoformat(),
        )

    async def search_files(
        self,
        *,
        query: str,
        path: str | None = None,
        path_prefix: str | None = None,
    ) -> list[FileSearchMatch]:
        normalized_query = query.strip()
        if normalized_query == "":
            raise ApiError(
                status_code=422,
                code="files.empty_search_query",
                message="Search query must not be empty.",
                retryable=False,
            )

        if path is not None:
            candidates = [await self.read_file(path)]
        else:
            files = await self.list_files(path_prefix=path_prefix)
            candidates = []
            for file_info in files:
                candidates.append(await self.read_file(file_info.path))

        needle = normalized_query.casefold()
        matches: list[FileSearchMatch] = []
        for file_content in candidates:
            for line_number, line in enumerate(file_content.content.splitlines(), start=1):
                if needle in line.casefold():
                    matches.append(
                        FileSearchMatch(
                            path=file_content.path,
                            line=line_number,
                            text=line,
                        )
                    )
                    if len(matches) >= MAX_SEARCH_MATCHES:
                        return matches

        return matches

    async def _iter_matching_api_paths(self, allowed_glob: str) -> list[str]:
        normalized_glob = self._path_policy.normalize_api_path(allowed_glob)
        if not any(token in normalized_glob for token in ("*", "?", "[")):
            return [normalized_glob]

        base = normalized_glob.split("*", 1)[0].rsplit("/", 1)[0]
        try:
            base_resolved = self._path_policy.resolve_prefix(base)
        except ApiError:
            return []

        matches: list[str] = []
        for relative_path in await self._backend.list_files(base_resolved):
            api_path = self._path_policy.relative_to_api_path(relative_path)
            if self._path_policy.matches_glob(api_path, normalized_glob):
                matches.append(api_path)
        return matches

    def _hash_content(self, content: str) -> str:
        return sha256(content.encode("utf-8")).hexdigest()
