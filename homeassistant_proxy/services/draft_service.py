from __future__ import annotations

from datetime import UTC, datetime
from sqlite3 import Row
from uuid import uuid4

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.db.session import SqliteStore
from homeassistant_proxy.models.api_models import (
    ApplyResult,
    ConfirmedActionRequest,
    CreateDraftRequest,
    Draft,
    DraftDiff,
    RollbackResult,
    ValidationCheck,
    ValidationResult,
)
from homeassistant_proxy.services.audit_service import AuditService
from homeassistant_proxy.services.backup_service import BackupService
from homeassistant_proxy.services.diff_service import create_unified_diff
from homeassistant_proxy.services.file_service import FileService
from homeassistant_proxy.services.reload_service import ReloadService
from homeassistant_proxy.services.validation_service import DraftValidationService


class DraftService:
    def __init__(self, settings: Settings, file_service: FileService, reload_service: ReloadService) -> None:
        self._settings = settings
        self._file_service = file_service
        self._reload_service = reload_service
        self._validation_service = DraftValidationService(settings)
        self._store = SqliteStore(settings.sqlite_path)
        self._backup_service = BackupService(settings)
        self._audit_service = AuditService(self._store)

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

    async def apply_draft(self, draft_id: str, request: ConfirmedActionRequest) -> ApplyResult:
        self._require_writes_enabled()
        draft = await self.get_draft(draft_id)
        if draft.status != "ready_for_approval":
            raise ApiError(
                status_code=409,
                code="drafts.invalid_status",
                message="Only drafts ready for approval can be applied.",
                retryable=False,
                details={"draft_id": draft_id, "status": draft.status},
            )

        validation = await self.validate_draft(draft_id)
        if not validation.ok:
            self._record_audit(
                action_type="apply_draft",
                resource_id=draft_id,
                request_summary=f"Apply draft for {draft.target_path}",
                result="failed",
                error_message="Draft validation failed before apply.",
            )
            raise ApiError(
                status_code=409,
                code="drafts.validation_failed",
                message="Draft validation failed before apply.",
                retryable=False,
                details={"errors": validation.errors},
            )

        previous_existed = await self._file_service.writable_file_exists(draft.target_path)
        if draft.operation_type == "create" and previous_existed:
            raise ApiError(
                status_code=409,
                code="drafts.target_already_exists",
                message="Create draft target already exists.",
                retryable=False,
                details={"path": draft.target_path},
            )
        if draft.operation_type == "update" and not previous_existed:
            raise ApiError(
                status_code=409,
                code="drafts.target_missing",
                message="Update draft target no longer exists.",
                retryable=False,
                details={"path": draft.target_path},
            )

        backup_id: str | None = None
        internal_backup_path: str | None = None
        previous_hash: str | None = None
        if previous_existed:
            current_file = await self._file_service.read_writable_file(draft.target_path)
            previous_hash = current_file.content_hash
            backup_id, internal_backup_path = self._backup_service.save_backup(
                draft_id=draft_id,
                target_path=draft.target_path,
                content=current_file.content,
            )
        else:
            backup_id = str(uuid4())

        await self._file_service.write_writable_file(draft.target_path, draft.proposed_content or "")
        post_validation = self._validation_service.validate_proposed_content(
            target_path=draft.target_path,
            proposed_content=draft.proposed_content or "",
        )
        applied_at = _now()
        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO file_versions (
                    id, path, content_hash, backup_path, previous_existed, created_at, related_draft_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    backup_id,
                    draft.target_path,
                    previous_hash,
                    internal_backup_path,
                    1 if previous_existed else 0,
                    applied_at,
                    draft_id,
                ),
            )

        if not post_validation.ok:
            self._mark_draft_failed(draft_id)
            self._record_audit(
                action_type="apply_draft",
                resource_id=draft_id,
                request_summary=f"Apply draft for {draft.target_path}",
                result="failed",
                error_message="Draft validation failed after write.",
            )
            raise ApiError(
                status_code=409,
                code="drafts.post_write_validation_failed",
                message="Draft validation failed after write. The backup is available for rollback.",
                retryable=False,
                details={"draft_id": draft_id, "backup_id": backup_id, "errors": post_validation.errors},
            )

        try:
            ha_validation = await self._reload_service.check_config()
        except ApiError as exc:
            self._mark_draft_failed(draft_id)
            self._record_audit(
                action_type="apply_draft",
                resource_id=draft_id,
                request_summary=f"Apply draft for {draft.target_path}",
                result="failed",
                error_message="Home Assistant configuration check failed to run after write.",
            )
            raise

        post_validation = _merge_validation_results(post_validation, ha_validation)
        if not post_validation.ok:
            self._mark_draft_failed(draft_id)
            self._record_audit(
                action_type="apply_draft",
                resource_id=draft_id,
                request_summary=f"Apply draft for {draft.target_path}",
                result="failed",
                error_message="Home Assistant configuration check failed after write.",
            )
            raise ApiError(
                status_code=409,
                code="drafts.ha_config_check_failed",
                message="Home Assistant configuration check failed after write. The backup is available for rollback.",
                retryable=False,
                details={"draft_id": draft_id, "backup_id": backup_id, "errors": post_validation.errors},
            )

        try:
            reload_result = await self._reload_service.reload_after_apply(post_validation)
        except ApiError as exc:
            self._mark_draft_failed(draft_id)
            self._record_audit(
                action_type="apply_draft",
                resource_id=draft_id,
                request_summary=f"Apply draft for {draft.target_path}",
                result="failed",
                error_message="Home Assistant reload failed after write.",
            )
            raise

        with self._store.connect() as connection:
            connection.execute(
                "UPDATE drafts SET status = ?, applied_at = ? WHERE id = ?",
                ("applied", applied_at, draft_id),
            )

        self._record_audit(
            action_type="apply_draft",
            resource_id=draft_id,
            request_summary=f"Apply draft for {draft.target_path}",
            result="ok",
            error_message=None,
        )
        return ApplyResult(
            ok=True,
            status="applied",
            draft_id=draft_id,
            backup_id=backup_id,
            backup_path=None,
            validation=post_validation,
            reload=reload_result,
            reload_executed=reload_result.ok and reload_result.action not in {"none", "restart_required"},
            restart_required=reload_result.action == "restart_required",
        )

    async def rollback_draft(self, draft_id: str, request: ConfirmedActionRequest) -> RollbackResult:
        self._require_writes_enabled()
        draft = await self.get_draft(draft_id)
        if draft.status not in {"applied", "failed"}:
            raise ApiError(
                status_code=409,
                code="drafts.invalid_status",
                message="Only applied or failed drafts can be rolled back.",
                retryable=False,
                details={"draft_id": draft_id, "status": draft.status},
            )

        version = self._latest_file_version(draft_id)
        if version is None:
            raise ApiError(
                status_code=409,
                code="drafts.backup_not_found",
                message="No backup record exists for this draft.",
                retryable=False,
                details={"draft_id": draft_id},
            )

        restored_hash: str | None = None
        if bool(version["previous_existed"]):
            backup_path = version["backup_path"]
            if backup_path is None:
                raise ApiError(
                    status_code=409,
                    code="drafts.backup_not_found",
                    message="Backup content is missing for this draft.",
                    retryable=False,
                    details={"draft_id": draft_id},
                )
            backup_content = self._backup_service.read_backup(backup_path)
            restored = await self._file_service.write_writable_file(draft.target_path, backup_content)
            restored_hash = restored.content_hash
            message = "Restored previous file content."
        else:
            if await self._file_service.writable_file_exists(draft.target_path):
                await self._file_service.delete_writable_file(draft.target_path)
            message = "Removed file created by draft."

        with self._store.connect() as connection:
            connection.execute(
                "UPDATE drafts SET status = ? WHERE id = ?",
                ("rolled_back", draft_id),
            )

        self._record_audit(
            action_type="rollback_draft",
            resource_id=draft_id,
            request_summary=f"Rollback draft for {draft.target_path}",
            result="ok",
            error_message=None,
        )
        return RollbackResult(ok=True, draft_id=draft_id, restored_hash=restored_hash, message=message)

    def _raise_if_invalid(self, validation: ValidationResult) -> None:
        if not validation.ok:
            raise ApiError(
                status_code=422,
                code="drafts.validation_failed",
                message="Draft validation failed.",
                retryable=False,
                details={"errors": validation.errors},
            )

    def _require_writes_enabled(self) -> None:
        if self._settings.readonly_mode:
            raise ApiError(
                status_code=403,
                code="drafts.readonly_mode",
                message="Read-only mode blocks apply and rollback operations.",
                retryable=False,
            )

    def _latest_file_version(self, draft_id: str) -> Row | None:
        with self._store.connect() as connection:
            return connection.execute(
                """
                SELECT * FROM file_versions
                WHERE related_draft_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (draft_id,),
            ).fetchone()

    def _mark_draft_failed(self, draft_id: str) -> None:
        with self._store.connect() as connection:
            connection.execute(
                "UPDATE drafts SET status = ? WHERE id = ?",
                ("failed", draft_id),
            )

    def _record_audit(
        self,
        *,
        action_type: str,
        resource_id: str,
        request_summary: str,
        result: str,
        error_message: str | None,
    ) -> None:
        self._audit_service.record(
            action_type=action_type,
            resource_type="draft",
            resource_id=resource_id,
            request_summary=request_summary,
            result=result,
            error_message=error_message,
            created_at=_now(),
            actor=self._settings.actor_name,
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


def _merge_validation_results(primary: ValidationResult, secondary: ValidationResult) -> ValidationResult:
    return ValidationResult(
        ok=primary.ok and secondary.ok,
        yaml_valid=primary.yaml_valid,
        path_allowed=primary.path_allowed,
        jinja_parse_status=primary.jinja_parse_status,
        estimated_reload_mode=primary.estimated_reload_mode if primary.ok and secondary.ok else "none",
        warnings=[*primary.warnings, *secondary.warnings],
        errors=[*primary.errors, *secondary.errors],
        checks=[*primary.checks, *secondary.checks],
    )


def _not_found(draft_id: str) -> ApiError:
    return ApiError(
        status_code=404,
        code="drafts.not_found",
        message="The requested draft was not found.",
        retryable=False,
        details={"draft_id": draft_id},
    )
