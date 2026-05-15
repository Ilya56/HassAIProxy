from __future__ import annotations

from datetime import UTC, datetime
from sqlite3 import Row
from uuid import uuid4

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.db.session import SqliteStore
from homeassistant_proxy.models.api_models import CreateDraftRequest, Draft, DraftDiff, ValidationCheck, ValidationResult
from homeassistant_proxy.services.diff_service import create_unified_diff
from homeassistant_proxy.services.file_service import FileService
from homeassistant_proxy.services.validation_service import DraftValidationService


class DraftService:
    def __init__(self, settings: Settings, file_service: FileService) -> None:
        self._settings = settings
        self._file_service = file_service
        self._validation_service = DraftValidationService(settings)
        self._store = SqliteStore(settings.sqlite_path)

    async def create_draft(self, request: CreateDraftRequest) -> Draft:
        if request.operation_type == "delete":
            raise ApiError(
                status_code=422,
                code="drafts.delete_not_supported",
                message="Delete drafts are not supported in v1.",
                retryable=False,
            )

        target_path = self._file_service.normalize_writable_path(request.target_path)
        validation = self._validation_service.validate_proposed_content(
            target_path=target_path,
            proposed_content=request.proposed_content,
        )
        self._raise_if_invalid(validation)

        base_content = ""
        base_hash: str | None = None
        if request.operation_type == "create":
            if await self._file_service.writable_file_exists(target_path):
                raise ApiError(
                    status_code=409,
                    code="drafts.target_already_exists",
                    message="Create draft target already exists.",
                    retryable=False,
                    details={"path": target_path},
                )
        elif request.operation_type == "update":
            if request.base_hash is None or request.base_hash.strip() == "":
                raise ApiError(
                    status_code=422,
                    code="drafts.base_hash_required",
                    message="Update drafts require base_hash from the current file content.",
                    retryable=False,
                    details={"path": target_path},
                )
            current_file = await self._file_service.read_writable_file(target_path)
            if current_file.content_hash != request.base_hash:
                raise ApiError(
                    status_code=409,
                    code="drafts.base_hash_mismatch",
                    message="The target file has changed since it was read.",
                    retryable=False,
                    details={"path": target_path},
                )
            base_content = current_file.content
            base_hash = request.base_hash

        draft_id = str(uuid4())
        created_at = _now()
        diff_text = create_unified_diff(
            target_path=target_path,
            base_content=base_content,
            proposed_content=request.proposed_content,
        )

        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO drafts (
                    id, target_path, operation_type, base_hash, proposed_content, diff_text,
                    summary, reason, status, created_at, validated_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    target_path,
                    request.operation_type,
                    base_hash,
                    request.proposed_content,
                    diff_text,
                    request.summary,
                    request.reason,
                    "ready_for_approval",
                    created_at,
                    created_at,
                    self._settings.actor_name,
                ),
            )

        return await self.get_draft(draft_id)

    async def get_draft(self, draft_id: str) -> Draft:
        with self._store.connect() as connection:
            row = connection.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise _not_found(draft_id)
        return _row_to_draft(row)

    async def get_diff(self, draft_id: str) -> DraftDiff:
        draft = await self.get_draft(draft_id)
        return DraftDiff(
            draft_id=draft.id,
            diff_text=draft.diff_text or "",
            summary=draft.summary or "",
        )

    async def validate_draft(self, draft_id: str) -> ValidationResult:
        draft = await self.get_draft(draft_id)
        validation = self._validation_service.validate_proposed_content(
            target_path=draft.target_path,
            proposed_content=draft.proposed_content or "",
        )
        if validation.ok and draft.operation_type == "update":
            if draft.base_hash is None:
                validation.ok = False
                validation.errors.append("Update draft is missing base_hash.")
                validation.checks.append(
                    ValidationCheck(name="base_hash", ok=False, message="Update drafts require base_hash.")
                )
            else:
                current_file = await self._file_service.read_writable_file(draft.target_path)
                hash_ok = current_file.content_hash == draft.base_hash
                validation.checks.append(
                    ValidationCheck(
                        name="base_hash",
                        ok=hash_ok,
                        message="Current file hash must match the draft base hash.",
                    )
                )
                if not hash_ok:
                    validation.ok = False
                    validation.errors.append("The target file has changed since draft creation.")
        return validation

    def _raise_if_invalid(self, validation: ValidationResult) -> None:
        if not validation.ok:
            raise ApiError(
                status_code=422,
                code="drafts.validation_failed",
                message="Draft validation failed.",
                retryable=False,
                details={"errors": validation.errors},
            )


def _row_to_draft(row: Row) -> Draft:
    return Draft(
        id=row["id"],
        target_path=row["target_path"],
        operation_type=row["operation_type"],
        base_hash=row["base_hash"],
        proposed_content=row["proposed_content"],
        diff_text=row["diff_text"],
        summary=row["summary"],
        reason=row["reason"],
        status=row["status"],
        created_at=row["created_at"],
        validated_at=row["validated_at"],
        applied_at=row["applied_at"],
        created_by=row["created_by"],
    )


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _not_found(draft_id: str) -> ApiError:
    return ApiError(
        status_code=404,
        code="drafts.not_found",
        message="The requested draft was not found.",
        retryable=False,
        details={"draft_id": draft_id},
    )
