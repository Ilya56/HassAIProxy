from fastapi import APIRouter

from homeassistant_proxy.dependencies import Authenticated, DraftServiceDep
from homeassistant_proxy.models.api_models import (
    ApplyResult,
    ConfirmedActionRequest,
    CreateDraftRequest,
    Draft,
    DraftDiff,
    RollbackResult,
    ValidationResult,
)

router = APIRouter(prefix="/drafts", tags=["Drafts"])


@router.post("/create", response_model=Draft, status_code=201, operation_id="createDraft")
async def create_draft(_: Authenticated, draft_service: DraftServiceDep, request: CreateDraftRequest) -> Draft:
    return await draft_service.create_draft(request)


@router.get("/{draft_id}", response_model=Draft, operation_id="getDraft")
async def get_draft(_: Authenticated, draft_service: DraftServiceDep, draft_id: str) -> Draft:
    return await draft_service.get_draft(draft_id)


@router.get("/{draft_id}/diff", response_model=DraftDiff, operation_id="getDraftDiff")
async def get_draft_diff(_: Authenticated, draft_service: DraftServiceDep, draft_id: str) -> DraftDiff:
    return await draft_service.get_diff(draft_id)


@router.post("/{draft_id}/validate", response_model=ValidationResult, operation_id="validateDraft")
async def validate_draft(_: Authenticated, draft_service: DraftServiceDep, draft_id: str) -> ValidationResult:
    return await draft_service.validate_draft(draft_id)


@router.post("/{draft_id}/apply", response_model=ApplyResult, operation_id="applyDraft")
async def apply_draft(
    _: Authenticated,
    draft_service: DraftServiceDep,
    draft_id: str,
    request: ConfirmedActionRequest,
) -> ApplyResult:
    return await draft_service.apply_draft(draft_id, request)


@router.post("/{draft_id}/rollback", response_model=RollbackResult, operation_id="rollbackDraft")
async def rollback_draft(
    _: Authenticated,
    draft_service: DraftServiceDep,
    draft_id: str,
    request: ConfirmedActionRequest,
) -> RollbackResult:
    return await draft_service.rollback_draft(draft_id, request)
