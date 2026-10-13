"""Audit-trail read API -- the one place the frontend's Audit Trail / history
view should read from so a browser refresh reloads the same persisted
history from the backend instead of resetting to an empty in-memory list.

Read-only: every audit record is written exclusively by
app/repositories/audit_repository.py's log() calls, scattered across the
real action call sites (analysis job lifecycle, incident creation/status
changes, responder CRUD, SMS config changes, dispatch send/preview, test-SMS
attempts). This module never writes a record itself.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories.audit_repository import AuditRepository, get_audit_repository
from app.repositories.mongo_job_repository import MongoDBUnavailableError
from app.schemas.analysis import AuditLogEntry

router = APIRouter(prefix="/v1/audit", tags=["Audit"])


def _get_audit_repository() -> AuditRepository:
    return get_audit_repository()


@router.get("", response_model=list[AuditLogEntry])
def list_audit_log(
    limit: int = 50,
    before: str | None = None,
    event_type: str | None = None,
    actor: str | None = None,
    correlation_id: str | None = None,
    repo: AuditRepository = Depends(_get_audit_repository),
) -> list[AuditLogEntry]:
    """Most-recent audit records first. Returns [] when none exist yet --
    never fabricated rows, and a genuine database outage reports a truthful
    503 rather than an empty list that could be mistaken for "no events"."""
    try:
        docs = repo.list(
            limit=limit,
            before=before,
            event_type=event_type,
            actor=actor,
            correlation_id=correlation_id,
        )
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The audit log database is temporarily unavailable; history cannot be read.",
        )
    return [AuditLogEntry(**doc) for doc in docs]
