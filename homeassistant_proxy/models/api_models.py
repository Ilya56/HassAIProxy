from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(pattern="^ok$")
    version: str
    ha_reachable: bool
    file_storage_ok: bool


class CapabilitiesResponse(BaseModel):
    read_only_mode: bool
    allowed_read_globs: list[str]
    allowed_write_globs: list[str]
    allowed_ha_services: list[str]
    action_levels: dict[str, str]


class HaConfigResponse(BaseModel):
    location_name: str
    time_zone: str | None = None
    unit_system: dict[str, object] | None = None
    version: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, object]
    retryable: bool
