"""Incident + detection-event read API.

Incidents are auto-created by app/services/analysis_service.py when a job
completes with anomaly_detected=True (see
app/repositories/incident_repository.py's module docstring) -- this module
only reads them back and allows an operator to change an incident's status
(e.g. "open" -> "acknowledged" -> "resolved"). Nothing here creates an
incident, runs inference, or sends a dispatch/SMS.

Detection events are a queryable fan-out of a job's temporal-evidence
windows (see app/repositories/detection_event_repository.py) -- read-only
here, created only from analysis_service.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories.audit_repository import AuditRepository, get_audit_repository
from app.repositories.detection_event_repository import DetectionEventRepository, get_detection_event_repository
from app.repositories.incident_repository import IncidentRepository, get_incident_repository
from app.core.config import get_settings
from app.repositories.mongo_job_repository import MongoDBUnavailableError
from app.schemas.analysis import DetectionEventResponse, IncidentResponse, IncidentUpdateStatusRequest
from app.schemas.incident_summary import LatestIncidentAiSummaryResponse, LatestIncidentSummaryResponse
from app.services.grok_summary_service import GrokSummaryService
from app.services.incident_summary_service import build_incident_summary

router = APIRouter(prefix="/v1/incidents", tags=["Incidents"])

_VALID_STATUSES = {"open", "acknowledged", "resolved"}

_MONGO_UNAVAILABLE_DETAIL = (
    "The incident database is temporarily unavailable. This does not affect "
    "video analysis or detection -- only incident records are affected."
)

# Module-level singleton, not constructed per-request: GrokSummaryService's
# whole point is its small in-process result cache (see its own docstring),
# which must survive across requests to actually avoid re-calling Grok on
# every dashboard poll/render. A fresh instance per request would silently
# defeat that cache every time.
_grok_summary_service: GrokSummaryService | None = None


def _get_grok_summary_service() -> GrokSummaryService:
    global _grok_summary_service
    if _grok_summary_service is None:
        _grok_summary_service = GrokSummaryService(get_settings())
    return _grok_summary_service


def _get_incident_repository() -> IncidentRepository:
    return get_incident_repository()


def _get_detection_event_repository() -> DetectionEventRepository:
    return get_detection_event_repository()


def _get_audit_repository() -> AuditRepository:
    return get_audit_repository()


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    status_filter: str | None = None,
    limit: int = 50,
    before: str | None = None,
    repo: IncidentRepository = Depends(_get_incident_repository),
) -> list[IncidentResponse]:
    """Most-recently-created incidents first. Returns [] when none exist --
    never fabricated rows. `status_filter` (query param name avoids
    shadowing the fastapi `status` module import) narrows to one status."""
    try:
        docs = repo.list(status=status_filter, limit=limit, before=before)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    return [IncidentResponse(**doc) for doc in docs]


def _load_latest_incident_and_job(
    repo: IncidentRepository,
) -> tuple[dict, dict | None] | None:
    """Shared by get_latest_incident_summary and get_latest_incident_ai_summary
    -- both need "the single most recent incident, plus its linked analysis
    job if readable." Returns None when there is no incident yet (a normal
    state, not an error). Raises MongoDBUnavailableError only when the
    incidents database itself is unreachable -- a missing/unreadable linked
    job degrades to job=None instead, exactly as before this extraction.
    """
    docs = repo.list(limit=1)
    if not docs:
        return None

    incident_doc = docs[0]

    job: dict | None = None
    job_id = incident_doc.get("job_id")
    if job_id:
        try:
            # Local import: avoids a module-import-time dependency between
            # the incidents and analysis route modules (both are only
            # wired together via FastAPI's router registration in
            # app/main.py, not via direct imports elsewhere) while still
            # reusing the exact same job-repository accessor
            # GET /v1/analysis/{job_id}/result relies on internally,
            # rather than duplicating its selection logic (Mongo vs
            # LOCAL_DEMO_MODE in-memory) here.
            from app.api.routes.analysis import get_job_repository

            job_repository = get_job_repository(get_settings())
            job_result = job_repository.get(job_id)
            if job_result is not None:
                job = job_result.model_dump(mode="json")
        except MongoDBUnavailableError:
            job = None
        except Exception:  # noqa: BLE001 -- a degraded summary must never fail this request
            job = None

    return incident_doc, job


@router.get("/latest/summary", response_model=LatestIncidentSummaryResponse)
def get_latest_incident_summary(
    repo: IncidentRepository = Depends(_get_incident_repository),
) -> LatestIncidentSummaryResponse:
    """The single most recent incident, plus a deterministic summary built
    from it and its linked analysis job (see
    app/services/incident_summary_service.py).

    No incidents yet -> {"incident": None, "summary": None}, 200 -- this is
    a normal state, not an error, matching list_incidents()'s own
    empty-list-is-not-an-error philosophy.

    If the incident itself exists but its linked job cannot be read (job
    not found, or the analysis-job database is unavailable), the summary
    still degrades gracefully (job=None passed to build_incident_summary)
    rather than failing the whole request -- the incident record itself was
    readable. Only a failure of the incidents database itself raises 503.
    """
    try:
        loaded = _load_latest_incident_and_job(repo)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)

    if loaded is None:
        return LatestIncidentSummaryResponse(incident=None, summary=None)

    incident_doc, job = loaded
    summary = build_incident_summary(incident_doc, job)
    return LatestIncidentSummaryResponse(
        incident=IncidentResponse(**incident_doc),
        summary=summary,
    )


@router.get("/latest/summary/ai", response_model=LatestIncidentAiSummaryResponse)
def get_latest_incident_ai_summary(
    force_refresh: bool = False,
    repo: IncidentRepository = Depends(_get_incident_repository),
) -> LatestIncidentAiSummaryResponse:
    """Powers the AI COPILOT tab: the same latest-incident summary as
    /latest/summary, plus a Grok (xAI)-generated prose summary of it (see
    app/services/grok_summary_service.py). Grok is given ONLY the already-
    structured, already-honest summary shape -- never the raw incident/job
    document, never responder data.

    No incidents yet -> every field None, 200 -- a normal empty state.
    When Grok is disabled/unconfigured or the live call fails, `summary_text`
    is still populated with a deterministic, non-fabricated fallback and
    `ai_summary_source` is "fallback" (never silently "grok") so the
    frontend can show the operator which one they're looking at.
    `force_refresh=true` bypasses the summarizer's small result cache for
    an explicit operator-triggered refresh.
    """
    try:
        loaded = _load_latest_incident_and_job(repo)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)

    if loaded is None:
        return LatestIncidentAiSummaryResponse(
            incident=None, summary=None, ai_summary_text=None, ai_summary_source=None, ai_summary_error=None
        )

    incident_doc, job = loaded
    summary = build_incident_summary(incident_doc, job)

    grok_service = _get_grok_summary_service()
    grok_result = grok_service.summarize_incident(incident_doc, job, force_refresh=force_refresh)

    return LatestIncidentAiSummaryResponse(
        incident=IncidentResponse(**incident_doc),
        summary=summary,
        ai_summary_text=grok_result.summary_text,
        ai_summary_source=grok_result.source,
        ai_summary_error=grok_result.error,
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: str,
    repo: IncidentRepository = Depends(_get_incident_repository),
) -> IncidentResponse:
    try:
        doc = repo.get(incident_id)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown incident_id: {incident_id}")
    return IncidentResponse(**doc)


@router.put("/{incident_id}/status", response_model=IncidentResponse)
def update_incident_status(
    incident_id: str,
    request: IncidentUpdateStatusRequest,
    repo: IncidentRepository = Depends(_get_incident_repository),
    audit_repo: AuditRepository = Depends(_get_audit_repository),
) -> IncidentResponse:
    """Explicit operator status change -- e.g. acknowledging or resolving an
    incident. Never sends a notification; purely a record update."""
    normalized = request.status.strip().lower()
    if normalized not in _VALID_STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid status '{request.status}'. Must be one of: {', '.join(sorted(_VALID_STATUSES))}.",
        )
    try:
        doc = repo.update_status(incident_id, normalized)
    except MongoDBUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _MONGO_UNAVAILABLE_DETAIL)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown incident_id: {incident_id}")
    audit_repo.log(
        "incident_status_changed",
        module="incidents",
        resource_type="incident",
        resource_id=incident_id,
        correlation_id=doc.get("job_id"),
        summary=f"Incident {incident_id} status changed to '{normalized}'.",
        details={"status": normalized},
    )
    return IncidentResponse(**doc)


@router.get("/by-job/{job_id}/detection-events", response_model=list[DetectionEventResponse])
def list_detection_events_for_job(
    job_id: str,
    repo: DetectionEventRepository = Depends(_get_detection_event_repository),
) -> list[DetectionEventResponse]:
    """Detection events for one job, in window order. Returns [] for a
    clean (non-anomalous) job or one with no persisted events -- never
    fabricated."""
    try:
        docs = repo.list_for_job(job_id)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The detection-event database is temporarily unavailable.",
        )
    docs.sort(key=lambda d: d.get("window_index", 0))
    return [DetectionEventResponse(**doc) for doc in docs]
