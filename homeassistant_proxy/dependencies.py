from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from homeassistant_proxy.config import Settings, get_settings
from homeassistant_proxy.core.auth import require_api_key
from homeassistant_proxy.services.ha_client import HomeAssistantClient

Authenticated = Annotated[None, Depends(require_api_key)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_ha_client(settings: SettingsDep) -> AsyncIterator[HomeAssistantClient]:
    client = HomeAssistantClient.from_settings(settings)
    try:
        yield client
    finally:
        await client.aclose()


HaClientDep = Annotated[HomeAssistantClient, Depends(get_ha_client)]
