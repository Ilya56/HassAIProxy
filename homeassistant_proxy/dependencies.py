from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from homeassistant_proxy.config import Settings, get_settings
from homeassistant_proxy.core.auth import require_api_key
from homeassistant_proxy.db.session import SqliteStore
from homeassistant_proxy.services.audit_service import AuditService
from homeassistant_proxy.services.draft_service import DraftService
from homeassistant_proxy.services.file_service import FileService
from homeassistant_proxy.services.ha_client import HomeAssistantClient
from homeassistant_proxy.services.reload_service import ReloadService

Authenticated = Annotated[None, Depends(require_api_key)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_ha_client(settings: SettingsDep) -> AsyncIterator[HomeAssistantClient]:
    client = HomeAssistantClient.from_settings(settings)
    try:
        yield client
    finally:
        await client.aclose()


HaClientDep = Annotated[HomeAssistantClient, Depends(get_ha_client)]


def get_file_service(settings: SettingsDep) -> FileService:
    return FileService(settings)


FileServiceDep = Annotated[FileService, Depends(get_file_service)]


def get_audit_service(settings: SettingsDep) -> AuditService:
    return AuditService(SqliteStore(settings.sqlite_path))


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


def get_reload_service(settings: SettingsDep, ha_client: HaClientDep) -> ReloadService:
    return ReloadService(settings, ha_client)


ReloadServiceDep = Annotated[ReloadService, Depends(get_reload_service)]


def get_draft_service(
    settings: SettingsDep,
    file_service: FileServiceDep,
    reload_service: ReloadServiceDep,
) -> DraftService:
    return DraftService(settings, file_service, reload_service)


DraftServiceDep = Annotated[DraftService, Depends(get_draft_service)]
