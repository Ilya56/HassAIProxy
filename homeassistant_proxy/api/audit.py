from fastapi import APIRouter, Query

from homeassistant_proxy.dependencies import AuditServiceDep, Authenticated
from homeassistant_proxy.models.api_models import AuditLog, AuditLogListResponse

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/logs", response_model=AuditLogListResponse, operation_id="listAuditLogs")
async def list_audit_logs(
    _: Authenticated,
    audit_service: AuditServiceDep,
    action_type: str | None = None,
    resource_type: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditLogListResponse:
    return AuditLogListResponse(
        logs=audit_service.list_logs(
            action_type=action_type,
            resource_type=resource_type,
            status=status,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    )


@router.get("/logs/{log_id}", response_model=AuditLog, operation_id="getAuditLog")
async def get_audit_log(_: Authenticated, audit_service: AuditServiceDep, log_id: str) -> AuditLog:
    return audit_service.get_log(log_id)
