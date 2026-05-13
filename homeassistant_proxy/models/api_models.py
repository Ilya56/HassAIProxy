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


class FileInfo(BaseModel):
    path: str
    writable: bool
    size_bytes: int | None = None
    content_hash: str | None = None
    modified_at: str | None = None


class FileListResponse(BaseModel):
    files: list[FileInfo]


class FileContent(BaseModel):
    path: str
    content: str
    content_hash: str


class FileSearchMatch(BaseModel):
    path: str
    line: int
    text: str


class FileSearchResponse(BaseModel):
    matches: list[FileSearchMatch]


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, object]
    retryable: bool
