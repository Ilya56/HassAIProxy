from typing import Literal

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


class EntitySummary(BaseModel):
    entity_id: str
    domain: str | None = None
    friendly_name: str | None = None
    state: str | None = None


class EntityListResponse(BaseModel):
    entities: list[EntitySummary]


class AutomationListResponse(BaseModel):
    automations: list[EntitySummary]


class ScriptListResponse(BaseModel):
    scripts: list[EntitySummary]


class EntityState(BaseModel):
    entity_id: str
    state: str
    attributes: dict[str, object]
    last_changed: str
    last_updated: str


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


DraftOperationType = Literal["create", "update", "delete"]
DraftStatus = Literal["draft", "validated", "ready_for_approval", "applied", "failed", "rolled_back", "superseded"]
JinjaParseStatus = Literal["not_applicable", "ok", "warning", "error"]
EstimatedReloadMode = Literal["none", "automations", "scripts", "quick_reload_all", "restart_required"]


class CreateDraftRequest(BaseModel):
    target_path: str
    operation_type: DraftOperationType
    base_hash: str | None = None
    proposed_content: str
    summary: str
    reason: str


class Draft(BaseModel):
    id: str
    target_path: str
    operation_type: DraftOperationType
    status: DraftStatus
    created_at: str
    created_by: str
    base_hash: str | None = None
    proposed_content: str | None = None
    diff_text: str | None = None
    summary: str | None = None
    reason: str | None = None
    validated_at: str | None = None
    applied_at: str | None = None


class DraftDiff(BaseModel):
    draft_id: str
    diff_text: str
    summary: str


class ValidationCheck(BaseModel):
    name: str
    ok: bool
    message: str | None = None


class ValidationResult(BaseModel):
    ok: bool
    checks: list[ValidationCheck]
    yaml_valid: bool | None = None
    path_allowed: bool | None = None
    jinja_parse_status: JinjaParseStatus | None = None
    estimated_reload_mode: EstimatedReloadMode | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ConfirmedActionRequest(BaseModel):
    confirmed: Literal[True]
    confirmation_text: str | None = None
    confirmation_note: str | None = None
    requested_by: str | None = None


class ReloadResult(BaseModel):
    ok: bool
    action: Literal["none", "automations", "scripts", "quick_reload_all", "restart_required"]
    message: str | None = None


class ApplyResult(BaseModel):
    ok: bool
    status: str
    draft_id: str
    validation: ValidationResult
    reload: ReloadResult
    backup_id: str | None = None
    backup_path: str | None = None
    reload_executed: bool = False
    restart_required: bool = False


class RollbackResult(BaseModel):
    ok: bool
    draft_id: str
    restored_hash: str | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, object]
    retryable: bool
