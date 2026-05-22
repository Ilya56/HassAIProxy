from __future__ import annotations

import asyncio
import logging
import stat
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol, TypeVar
from uuid import uuid4

import asyncssh
from asyncssh.constants import FXR_ATOMIC, FXR_OVERWRITE

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class FileBackendStat:
    size_bytes: int
    modified_at: datetime


class FileBackend(Protocol):
    async def list_files(self, relative_dir: str) -> list[str]: ...

    async def read_text(self, relative_path: str) -> str: ...

    async def stat(self, relative_path: str) -> FileBackendStat: ...

    async def check_access(self) -> None: ...

    async def write_text(self, relative_path: str, content: str) -> None: ...

    async def delete_file(self, relative_path: str) -> None: ...


class LocalFileBackend:
    def __init__(self, config_root: str) -> None:
        self._config_root = Path(config_root).expanduser().resolve()

    async def list_files(self, relative_dir: str) -> list[str]:
        root = self._resolve_dir(relative_dir)
        if not root.exists() or not root.is_dir():
            return []

        matches: list[str] = []
        for local_path in root.rglob("*"):
            if local_path.is_symlink() or not local_path.is_file():
                continue
            resolved = local_path.resolve()
            if not resolved.is_relative_to(self._config_root):
                continue
            matches.append(resolved.relative_to(self._config_root).as_posix())
        return matches

    async def read_text(self, relative_path: str) -> str:
        local_path = self._resolve_file(relative_path)
        return local_path.read_text(encoding="utf-8")

    async def write_text(self, relative_path: str, content: str) -> None:
        local_path = self._resolve_relative_path(relative_path, must_exist=False)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(content, encoding="utf-8")

    async def delete_file(self, relative_path: str) -> None:
        local_path = self._resolve_file(relative_path)
        local_path.unlink()

    async def stat(self, relative_path: str) -> FileBackendStat:
        local_path = self._resolve_file(relative_path)
        file_stat = local_path.stat()
        return FileBackendStat(
            size_bytes=file_stat.st_size,
            modified_at=datetime.fromtimestamp(file_stat.st_mtime, tz=UTC),
        )

    async def check_access(self) -> None:
        if not self._config_root.exists() or not self._config_root.is_dir():
            raise _not_found()

    def _resolve_dir(self, relative_dir: str) -> Path:
        return self._resolve_relative_path(relative_dir, must_exist=False)

    def _resolve_file(self, relative_path: str) -> Path:
        local_path = self._resolve_relative_path(relative_path, must_exist=True)
        if not local_path.is_file():
            raise _not_found()
        return local_path

    def _resolve_relative_path(self, relative_path: str, *, must_exist: bool) -> Path:
        parts = _validate_relative_path(relative_path)
        candidate_path = self._config_root.joinpath(*parts)
        local_path = candidate_path.resolve()
        if not local_path.is_relative_to(self._config_root):
            raise _forbidden_path_escape()
        if candidate_path.exists() and candidate_path.absolute() != local_path:
            raise _forbidden_path_escape()
        if must_exist and not local_path.exists():
            raise _not_found()
        return local_path


class SftpFileBackend:
    def __init__(self, settings: Settings) -> None:
        if not settings.sftp_host:
            raise ApiError(
                status_code=500,
                code="files.sftp_not_configured",
                message="SFTP file backend requires SFTP_HOST.",
                retryable=False,
            )
        if not settings.sftp_private_key_path:
            raise ApiError(
                status_code=500,
                code="files.sftp_not_configured",
                message="SFTP file backend requires SFTP_PRIVATE_KEY_PATH.",
                retryable=False,
            )

        self._host = settings.sftp_host
        self._port = settings.sftp_port
        self._username = settings.sftp_username
        self._private_key_path = settings.sftp_private_key_path
        self._private_key_passphrase = settings.sftp_private_key_passphrase or None
        self._remote_root = _normalize_remote_root(settings.sftp_root)
        self._timeout = settings.request_timeout_seconds

    async def list_files(self, relative_dir: str) -> list[str]:
        return await self._with_timeout(self._list_files(relative_dir), operation="list_files")

    async def _list_files(self, relative_dir: str) -> list[str]:
        remote_dir = self._remote_path(relative_dir)
        async with self._sftp_client() as sftp:
            try:
                return await self._list_files_recursive(sftp, remote_dir, relative_dir.strip("/"))
            except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPNoSuchPath, asyncssh.SFTPNotADirectory):
                return []
            except ApiError:
                raise
            except Exception as exc:
                raise _transport_error(exc, operation="list_files") from exc

    async def read_text(self, relative_path: str) -> str:
        return await self._with_timeout(self._read_text(relative_path), operation="read_text")

    async def write_text(self, relative_path: str, content: str) -> None:
        await self._with_timeout(self._write_text(relative_path, content), operation="write_text")

    async def delete_file(self, relative_path: str) -> None:
        await self._with_timeout(self._delete_file(relative_path), operation="delete_file")

    async def _read_text(self, relative_path: str) -> str:
        remote_path = self._remote_path(relative_path)
        async with self._sftp_client() as sftp:
            await self._assert_safe_remote_file(sftp, remote_path)
            try:
                async with sftp.open(remote_path, "rb") as remote_file:
                    content = await remote_file.read()
            except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPNoSuchPath) as exc:
                raise _not_found() from exc
            except ApiError:
                raise
            except Exception as exc:
                raise _transport_error(exc, operation="read_text") from exc

        return content.decode("utf-8")

    async def _write_text(self, relative_path: str, content: str) -> None:
        remote_path = self._remote_path(relative_path)
        parent_relative = _parent_relative_path(relative_path)
        parent_remote = self._remote_path(parent_relative)
        temp_remote_path = _temporary_remote_path(remote_path)

        async with self._sftp_client() as sftp:
            try:
                await self._ensure_safe_remote_dir(sftp, parent_relative)
                await self._assert_safe_write_target(sftp, remote_path)
                async with sftp.open(temp_remote_path, "wb") as remote_file:
                    await remote_file.write(content.encode("utf-8"))
                await self._assert_safe_remote_file(sftp, temp_remote_path)
                await sftp.rename(temp_remote_path, remote_path, FXR_OVERWRITE | FXR_ATOMIC)
                await self._ensure_safe_remote_dir(sftp, parent_relative)
            except ApiError:
                raise
            except Exception as exc:
                raise _transport_error(exc, operation="write_text") from exc
            finally:
                await self._remove_temp_file_if_present(sftp, temp_remote_path, parent_remote)

    async def _delete_file(self, relative_path: str) -> None:
        remote_path = self._remote_path(relative_path)
        async with self._sftp_client() as sftp:
            await self._assert_safe_remote_file(sftp, remote_path)
            try:
                await sftp.remove(remote_path)
            except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPNoSuchPath) as exc:
                raise _not_found() from exc
            except ApiError:
                raise
            except Exception as exc:
                raise _transport_error(exc, operation="delete_file") from exc

    async def stat(self, relative_path: str) -> FileBackendStat:
        return await self._with_timeout(self._stat(relative_path), operation="stat")

    async def check_access(self) -> None:
        await self._with_timeout(self._check_access(), operation="check_access")

    async def _check_access(self) -> None:
        async with self._sftp_client() as sftp:
            try:
                attrs = await sftp.lstat(self._remote_root)
            except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPNoSuchPath) as exc:
                raise _not_found() from exc
            except ApiError:
                raise
            except Exception as exc:
                raise _transport_error(exc, operation="check_access") from exc

            permissions = attrs.permissions or 0
            if stat.S_ISLNK(permissions):
                raise _forbidden_path_escape()
            if not stat.S_ISDIR(permissions):
                raise _not_found()

            try:
                real_root = await sftp.realpath(self._remote_root)
            except ApiError:
                raise
            except Exception as exc:
                raise _transport_error(exc, operation="check_access") from exc
            if PurePosixPath(real_root).as_posix() != PurePosixPath(self._remote_root).as_posix():
                raise _forbidden_path_escape()

    async def _stat(self, relative_path: str) -> FileBackendStat:
        remote_path = self._remote_path(relative_path)
        async with self._sftp_client() as sftp:
            await self._assert_safe_remote_file(sftp, remote_path)
            try:
                attrs = await sftp.stat(remote_path)
            except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPNoSuchPath) as exc:
                raise _not_found() from exc
            except ApiError:
                raise
            except Exception as exc:
                raise _transport_error(exc, operation="stat") from exc

        return FileBackendStat(
            size_bytes=int(attrs.size or 0),
            modified_at=datetime.fromtimestamp(float(attrs.mtime or 0), tz=UTC),
        )

    @asynccontextmanager
    async def _sftp_client(self) -> AsyncIterator[asyncssh.SFTPClient]:
        logger.info(
            "sftp_connect_started host=%s port=%s username=%s root=%s timeout=%s",
            self._host,
            self._port,
            self._username,
            self._remote_root,
            self._timeout,
        )
        try:
            async with asyncssh.connect(
                self._host,
                port=self._port,
                username=self._username,
                client_keys=[self._private_key_path],
                passphrase=self._private_key_passphrase,
                connect_timeout=self._timeout,
            ) as connection:
                async with connection.start_sftp_client() as sftp:
                    logger.info("sftp_connect_succeeded host=%s root=%s", self._host, self._remote_root)
                    yield sftp
        except ApiError:
            raise
        except Exception as exc:
            raise _transport_error(exc, operation="connect") from exc

    async def _list_files_recursive(
        self,
        sftp: asyncssh.SFTPClient,
        remote_dir: str,
        relative_dir: str,
    ) -> list[str]:
        matches: list[str] = []
        for name in await sftp.listdir(remote_dir):
            if name in {".", ".."}:
                continue
            child_relative = _join_relative(relative_dir, name)
            child_remote = self._remote_path(child_relative)
            try:
                attrs = await sftp.lstat(child_remote)
            except asyncssh.Error:
                continue

            permissions = attrs.permissions or 0
            if stat.S_ISLNK(permissions):
                continue
            if stat.S_ISDIR(permissions):
                matches.extend(await self._list_files_recursive(sftp, child_remote, child_relative))
            elif stat.S_ISREG(permissions):
                matches.append(child_relative)
        return matches

    async def _assert_safe_remote_file(self, sftp: asyncssh.SFTPClient, remote_path: str) -> None:
        try:
            attrs = await sftp.lstat(remote_path)
        except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPNoSuchPath) as exc:
            logger.info(
                "sftp_remote_file_not_found operation=assert_safe_remote_file error_type=%s",
                type(exc).__name__,
            )
            raise _not_found() from exc
        except ApiError:
            raise
        except Exception as exc:
            raise _transport_error(exc, operation="assert_safe_remote_file") from exc

        permissions = attrs.permissions or 0
        if stat.S_ISLNK(permissions):
            raise _forbidden_path_escape()
        if not stat.S_ISREG(permissions):
            raise _not_found()

        try:
            real_path = await sftp.realpath(remote_path)
            real_root = await sftp.realpath(self._remote_root)
        except ApiError:
            raise
        except Exception as exc:
            raise _transport_error(exc, operation="assert_safe_remote_file") from exc
        if not _remote_path_is_under(real_path, real_root):
            raise _forbidden_path_escape()

    async def _assert_safe_write_target(self, sftp: asyncssh.SFTPClient, remote_path: str) -> None:
        try:
            await self._assert_safe_remote_file(sftp, remote_path)
        except ApiError as exc:
            if exc.code == "files.not_found":
                return
            raise

    async def _ensure_safe_remote_dir(self, sftp: asyncssh.SFTPClient, relative_dir: str) -> None:
        parts = _validate_relative_path(relative_dir)
        current_relative = ""
        for part in parts:
            current_relative = _join_relative(current_relative, part)
            current_remote = self._remote_path(current_relative)
            try:
                attrs = await sftp.lstat(current_remote)
            except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPNoSuchPath):
                try:
                    logger.info("sftp_create_remote_dir relative_dir=%s", current_relative)
                    await sftp.mkdir(current_remote)
                    attrs = await sftp.lstat(current_remote)
                except asyncssh.Error as exc:
                    raise _transport_error(exc, operation="ensure_safe_remote_dir") from exc
            except ApiError:
                raise
            except Exception as exc:
                raise _transport_error(exc, operation="ensure_safe_remote_dir") from exc

            permissions = attrs.permissions or 0
            if stat.S_ISLNK(permissions):
                raise _forbidden_path_escape()
            if not stat.S_ISDIR(permissions):
                raise _not_found()

        remote_dir = self._remote_path(relative_dir)
        try:
            real_path = await sftp.realpath(remote_dir)
            real_root = await sftp.realpath(self._remote_root)
        except ApiError:
            raise
        except Exception as exc:
            raise _transport_error(exc, operation="ensure_safe_remote_dir") from exc
        if not _remote_path_is_under(real_path, real_root):
            raise _forbidden_path_escape()

    async def _remove_temp_file_if_present(
        self,
        sftp: asyncssh.SFTPClient,
        temp_remote_path: str,
        parent_remote: str,
    ) -> None:
        if PurePosixPath(temp_remote_path).parent.as_posix() != PurePosixPath(parent_remote).as_posix():
            return
        try:
            attrs = await sftp.lstat(temp_remote_path)
        except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPNoSuchPath):
            return
        except asyncssh.Error:
            return

        permissions = attrs.permissions or 0
        if stat.S_ISREG(permissions):
            try:
                await sftp.remove(temp_remote_path)
            except asyncssh.Error:
                return

    def _remote_path(self, relative_path: str) -> str:
        parts = _validate_relative_path(relative_path)
        if not parts:
            return self._remote_root
        return f"{self._remote_root.rstrip('/')}/{'/'.join(parts)}"

    async def _with_timeout(self, awaitable: Awaitable[T], *, operation: str) -> T:
        try:
            return await asyncio.wait_for(awaitable, timeout=self._timeout)
        except TimeoutError as exc:
            raise ApiError(
                status_code=504,
                code="files.remote_transport_timeout",
                message="Remote file transport timed out.",
                retryable=True,
                details=_transport_details(exc, operation=operation),
            ) from exc


def build_file_backend(settings: Settings) -> FileBackend:
    if settings.file_backend == "local":
        return LocalFileBackend(settings.config_root)
    if settings.file_backend == "sftp":
        return SftpFileBackend(settings)

    raise ApiError(
        status_code=500,
        code="files.backend_not_configured",
        message="Configured file backend is not supported.",
        retryable=False,
        details={"file_backend": settings.file_backend},
    )


def _validate_relative_path(relative_path: str) -> tuple[str, ...]:
    if relative_path in {"", "."}:
        return ()

    path = PurePosixPath(relative_path.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise _forbidden_path_escape()
    return tuple(part for part in path.parts if part not in {"", "."})


def _normalize_remote_root(remote_root: str) -> str:
    root = PurePosixPath(remote_root.replace("\\", "/"))
    if not root.is_absolute() or ".." in root.parts:
        raise ApiError(
            status_code=500,
            code="files.sftp_not_configured",
            message="SFTP_ROOT must be an absolute remote path.",
            retryable=False,
        )
    return root.as_posix()


def _remote_path_is_under(remote_path: str, remote_root: str) -> bool:
    path = PurePosixPath(remote_path)
    root = PurePosixPath(remote_root)
    return path == root or root in path.parents


def _join_relative(parent: str, child: str) -> str:
    if parent == "":
        return child
    return f"{parent.rstrip('/')}/{child}"


def _parent_relative_path(relative_path: str) -> str:
    parts = _validate_relative_path(relative_path)
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])


def _temporary_remote_path(remote_path: str) -> str:
    path = PurePosixPath(remote_path)
    temp_name = f"{path.name}.tmp-{uuid4().hex}"
    return path.with_name(temp_name).as_posix()


def _transport_error(exc: BaseException, *, operation: str | None = None) -> ApiError:
    details = _transport_details(exc, operation=operation)
    logger.warning(
        "sftp_transport_error operation=%s error_type=%s details=%s",
        operation,
        type(exc).__name__,
        details,
    )
    return ApiError(
        status_code=502,
        code="files.remote_transport_error",
        message="Remote file transport failed.",
        retryable=True,
        details=details,
    )


def _transport_details(exc: BaseException, *, operation: str | None = None) -> dict[str, str]:
    details = {
        "backend": "sftp",
        "error_type": type(exc).__name__,
    }
    if operation is not None:
        details["operation"] = operation
    return details


def _forbidden_path_escape() -> ApiError:
    return ApiError(
        status_code=403,
        code="files.path_escape",
        message="The requested path escapes the configured Home Assistant config root.",
        retryable=False,
    )


def _not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code="files.not_found",
        message="The requested file was not found.",
        retryable=False,
    )
