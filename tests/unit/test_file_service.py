import asyncio
import stat
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hashlib import sha256

import asyncssh
import pytest
from asyncssh.constants import FXR_ATOMIC, FXR_OVERWRITE

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

    async def check_access(self) -> None:
        return None


class FakeSftpAttrs:
    def __init__(self, permissions: int, size: int = 0, mtime: float = 1_778_688_000.0) -> None:
        self.permissions = permissions
        self.size = size
        self.mtime = mtime


class FakeRemoteFile:
    def __init__(self, fake_sftp: "FakeSftpClient", path: str) -> None:
        self._fake_sftp = fake_sftp
        self._path = path

    async def __aenter__(self) -> "FakeRemoteFile":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    async def write(self, content: bytes) -> None:
        self._fake_sftp.files[self._path] = content


class FakeSftpClient:
    def __init__(self) -> None:
        self.dirs: set[str] = {"/config"}
        self.files: dict[str, bytes] = {}
        self.symlinks: set[str] = set()
        self.rename_flags: list[int] = []
        self.removed_paths: list[str] = []

    async def lstat(self, path: str) -> FakeSftpAttrs:
        if path in self.symlinks:
            return FakeSftpAttrs(stat.S_IFLNK)
        if path in self.dirs:
            return FakeSftpAttrs(stat.S_IFDIR)
        if path in self.files:
            return FakeSftpAttrs(stat.S_IFREG, size=len(self.files[path]))
        raise asyncssh.SFTPNoSuchFile(path)

    async def stat(self, path: str) -> FakeSftpAttrs:
        return await self.lstat(path)

    async def realpath(self, path: str) -> str:
        return path

    async def mkdir(self, path: str) -> None:
        parent = path.rsplit("/", 1)[0] or "/"
        if parent not in self.dirs:
            raise asyncssh.SFTPNoSuchPath(parent)
        self.dirs.add(path)

    def open(self, path: str, mode: str) -> FakeRemoteFile:
        assert mode == "wb"
        parent = path.rsplit("/", 1)[0] or "/"
        assert parent in self.dirs
        return FakeRemoteFile(self, path)

    async def rename(self, oldpath: str, newpath: str, flags: int = 0) -> None:
        if oldpath not in self.files:
            raise asyncssh.SFTPNoSuchFile(oldpath)
        self.rename_flags.append(flags)
        self.files[newpath] = self.files.pop(oldpath)

    async def remove(self, path: str) -> None:
        if path not in self.files:
            raise asyncssh.SFTPNoSuchFile(path)
        self.removed_paths.append(path)
        del self.files[path]


class FakeableSftpFileBackend(SftpFileBackend):
    def __init__(self, fake_sftp: FakeSftpClient) -> None:
        super().__init__(
            Settings(
                file_backend="sftp",
                sftp_host="homeassistant.local",
                sftp_private_key_path="./secrets/ha_proxy_sftp_key",
            )
        )
        self.fake_sftp = fake_sftp

    @asynccontextmanager
    async def _sftp_client(self) -> AsyncIterator[FakeSftpClient]:
        yield self.fake_sftp


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


def test_sftp_backend_passes_key_passphrase_to_asyncssh(monkeypatch) -> None:
    captured_kwargs = {}

    class FakeSftpContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

    class FakeConnection:
        async def __aenter__(self) -> "FakeConnection":
            return self

        async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

        def start_sftp_client(self) -> FakeSftpContext:
            return FakeSftpContext()

    def fake_connect(*args: object, **kwargs: object) -> FakeConnection:
        captured_kwargs.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr("homeassistant_proxy.services.file_backends.asyncssh.connect", fake_connect)
    backend = SftpFileBackend(
        Settings(
            file_backend="sftp",
            sftp_host="homeassistant.local",
            sftp_private_key_path="./secrets/ha_proxy_sftp_key",
            sftp_private_key_passphrase="test-passphrase",
        )
    )

    async def use_client() -> None:
        async with backend._sftp_client():
            pass

    asyncio.run(use_client())

    assert captured_kwargs["passphrase"] == "test-passphrase"


def test_sftp_backend_reports_connect_error_details(monkeypatch) -> None:
    def fake_connect(*args: object, **kwargs: object) -> object:
        raise OSError("debug failure")

    monkeypatch.setattr("homeassistant_proxy.services.file_backends.asyncssh.connect", fake_connect)
    backend = SftpFileBackend(
        Settings(
            file_backend="sftp",
            sftp_host="homeassistant.local",
            sftp_private_key_path="./secrets/ha_proxy_sftp_key",
        )
    )

    async def use_client() -> None:
        async with backend._sftp_client():
            pass

    with pytest.raises(ApiError) as exc_info:
        asyncio.run(use_client())

    assert exc_info.value.code == "files.remote_transport_error"
    assert exc_info.value.details == {
        "backend": "sftp",
        "error_type": "OSError",
        "operation": "connect",
    }


def test_sftp_backend_check_access_verifies_remote_root() -> None:
    fake_sftp = FakeSftpClient()
    backend = FakeableSftpFileBackend(fake_sftp)

    asyncio.run(backend.check_access())


def test_sftp_backend_check_access_rejects_missing_remote_root() -> None:
    fake_sftp = FakeSftpClient()
    fake_sftp.dirs.clear()
    backend = FakeableSftpFileBackend(fake_sftp)

    with pytest.raises(ApiError) as exc_info:
        asyncio.run(backend.check_access())

    assert exc_info.value.code == "files.not_found"


def test_file_service_check_storage_returns_false_on_backend_error() -> None:
    class BrokenBackend(MemoryFileBackend):
        async def check_access(self) -> None:
            raise ApiError(
                status_code=502,
                code="files.remote_transport_error",
                message="Remote file transport failed.",
                retryable=True,
            )

    service = FileService(Settings(), backend=BrokenBackend())

    assert asyncio.run(service.check_storage()) is False


def test_sftp_missing_parent_path_is_created_on_write() -> None:
    class MissingParentSftpClient(FakeSftpClient):
        async def lstat(self, path: str) -> FakeSftpAttrs:
            if path == "/config":
                return FakeSftpAttrs(stat.S_IFDIR)
            if path in self.dirs or path in self.files:
                return await super().lstat(path)
            raise asyncssh.SFTPNoSuchPath(path)

    fake_sftp = MissingParentSftpClient()
    service = FileService(Settings(), backend=FakeableSftpFileBackend(fake_sftp))

    exists = asyncio.run(service.writable_file_exists("/config/packages/ai/co2.yaml"))
    written = asyncio.run(service.write_writable_file("/config/packages/ai/co2.yaml", "automation: []\n"))

    assert exists is False
    assert written.path == "/config/packages/ai/co2.yaml"
    assert "/config/packages" in fake_sftp.dirs
    assert "/config/packages/ai" in fake_sftp.dirs
    assert fake_sftp.files["/config/packages/ai/co2.yaml"] == b"automation: []\n"


def test_sftp_backend_requires_host() -> None:
    settings = Settings(file_backend="sftp", sftp_private_key_path="./secrets/ha_proxy_sftp_key")

    with pytest.raises(ApiError) as exc_info:
        build_file_backend(settings)

    assert exc_info.value.code == "files.sftp_not_configured"


def test_sftp_backend_writes_through_temp_file_and_creates_parent_dirs() -> None:
    fake_sftp = FakeSftpClient()
    backend = FakeableSftpFileBackend(fake_sftp)

    asyncio.run(backend.write_text("packages/ai/co2.yaml", "automation: []\n"))

    assert "/config/packages" in fake_sftp.dirs
    assert "/config/packages/ai" in fake_sftp.dirs
    assert fake_sftp.files["/config/packages/ai/co2.yaml"] == b"automation: []\n"
    assert not [path for path in fake_sftp.files if ".tmp-" in path]
    assert fake_sftp.rename_flags == [FXR_OVERWRITE | FXR_ATOMIC]


def test_sftp_backend_write_rejects_symlink_target() -> None:
    fake_sftp = FakeSftpClient()
    fake_sftp.dirs.update({"/config/packages", "/config/packages/ai"})
    fake_sftp.symlinks.add("/config/packages/ai/co2.yaml")
    backend = FakeableSftpFileBackend(fake_sftp)

    with pytest.raises(ApiError) as exc_info:
        asyncio.run(backend.write_text("packages/ai/co2.yaml", "automation: []\n"))

    assert exc_info.value.code == "files.path_escape"
    assert fake_sftp.files == {}


def test_sftp_backend_delete_removes_regular_file() -> None:
    fake_sftp = FakeSftpClient()
    fake_sftp.dirs.update({"/config/packages", "/config/packages/ai"})
    fake_sftp.files["/config/packages/ai/co2.yaml"] = b"automation: []\n"
    backend = FakeableSftpFileBackend(fake_sftp)

    asyncio.run(backend.delete_file("packages/ai/co2.yaml"))

    assert "/config/packages/ai/co2.yaml" not in fake_sftp.files
    assert fake_sftp.removed_paths == ["/config/packages/ai/co2.yaml"]


def test_sftp_backend_delete_rejects_symlink_target() -> None:
    fake_sftp = FakeSftpClient()
    fake_sftp.dirs.update({"/config/packages", "/config/packages/ai"})
    fake_sftp.symlinks.add("/config/packages/ai/co2.yaml")
    backend = FakeableSftpFileBackend(fake_sftp)

    with pytest.raises(ApiError) as exc_info:
        asyncio.run(backend.delete_file("packages/ai/co2.yaml"))

    assert exc_info.value.code == "files.path_escape"
    assert fake_sftp.removed_paths == []


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
