import asyncio
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.models.api_models import FileContent, FileSearchMatch
from homeassistant_proxy.services.file_backends import FileBackendStat, SftpFileBackend, build_file_backend
from homeassistant_proxy.services.file_service import FileService


class MemoryFileBackend:
    def __init__(self) -> None:
        self.read_paths: list[str] = []
        self.stat_paths: list[str] = []

    async def list_files(self, relative_dir: str) -> list[str]:
        assert relative_dir == "packages/ai"
        return ["packages/ai/test.yaml", "packages/ai/skip.txt"]

    async def read_text(self, relative_path: str) -> str:
        self.read_paths.append(relative_path)
        return "automation: []\n"

    async def stat(self, relative_path: str) -> FileBackendStat:
        self.stat_paths.append(relative_path)
        return FileBackendStat(size_bytes=15, modified_at=datetime(2026, 5, 13, tzinfo=UTC))


def test_file_service_passes_validated_relative_path_to_backend() -> None:
    backend = MemoryFileBackend()
    service = FileService(Settings(), backend=backend)

    content = asyncio.run(service.read_file("/config/packages/ai/test.yaml"))

    assert content == FileContent(
        path="/config/packages/ai/test.yaml",
        content="automation: []\n",
        content_hash=sha256("automation: []\n".encode("utf-8")).hexdigest(),
    )
    assert backend.stat_paths == ["packages/ai/test.yaml"]
    assert backend.read_paths == ["packages/ai/test.yaml"]


def test_file_service_lists_files_through_backend_without_exposing_backend_paths() -> None:
    backend = MemoryFileBackend()
    settings = Settings(allowed_read_globs=["/config/packages/ai/*.yaml"])
    service = FileService(settings, backend=backend)

    files = asyncio.run(service.list_files(path_prefix="/config/packages/ai"))

    assert [file.path for file in files] == ["/config/packages/ai/test.yaml"]


def test_build_file_backend_creates_sftp_backend() -> None:
    settings = Settings(
        file_backend="sftp",
        sftp_host="homeassistant.local",
        sftp_private_key_path="./secrets/ha_proxy_sftp_key",
    )

    assert isinstance(build_file_backend(settings), SftpFileBackend)


def test_sftp_backend_requires_host() -> None:
    settings = Settings(file_backend="sftp", sftp_private_key_path="./secrets/ha_proxy_sftp_key")

    with pytest.raises(ApiError) as exc_info:
        build_file_backend(settings)

    assert exc_info.value.code == "files.sftp_not_configured"


def test_file_service_search_limits_matches_to_100() -> None:
    class ManyMatchesBackend(MemoryFileBackend):
        async def list_files(self, relative_dir: str) -> list[str]:
            return ["packages/ai/many.yaml"]

        async def read_text(self, relative_path: str) -> str:
            return "\n".join(["target"] * 101)

        async def stat(self, relative_path: str) -> FileBackendStat:
            return FileBackendStat(size_bytes=707, modified_at=datetime(2026, 5, 13, tzinfo=UTC))

    settings = Settings(allowed_read_globs=["/config/packages/ai/*.yaml"])
    service = FileService(settings, backend=ManyMatchesBackend())

    matches = asyncio.run(service.search_files(query="target"))

    assert len(matches) == 100
    assert matches[0] == FileSearchMatch(path="/config/packages/ai/many.yaml", line=1, text="target")
    assert matches[-1] == FileSearchMatch(path="/config/packages/ai/many.yaml", line=100, text="target")


def test_file_service_search_rejects_empty_query() -> None:
    service = FileService(Settings(), backend=MemoryFileBackend())

    with pytest.raises(ApiError) as exc_info:
        asyncio.run(service.search_files(query="  "))

    assert exc_info.value.code == "files.empty_search_query"
