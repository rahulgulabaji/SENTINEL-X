"""Analysis API routes: submit a video for analysis, check job status, and
fetch the completed result."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.core.mongodb import get_database
from app.repositories.mongo_job_repository import MongoDBUnavailableError, MongoJobRepository
from app.schemas.analysis import AnalysisJobSummary, AnalysisResult, AnalysisStatus
from app.services.analysis_service import run_analysis_job
from app.services.job_executor import InProcessJobExecutor, JobExecutor
from app.services.job_repository import InMemoryJobRepository, JobRepository

router = APIRouter(prefix="/v1/analysis", tags=["Analysis"])

# Single process-wide repository instance, built lazily on first use rather
# than at import time -- constructing a MongoClient is cheap/non-blocking,
# but doing it eagerly at module-import time (as the old
# InMemoryJobRepository harmlessly did) would run before any test fixture
# gets a chance to monkeypatch app.core.mongodb's singleton, breaking every
# test file that imports app.main regardless of whether it touches analysis
# jobs. Same lazy-singleton convention as every other repository accessor
# (get_mongo_responder_repository(), get_incident_repository(), etc).
#
# LOCAL_DEMO_MODE (see app/core/config.py, default False): when explicitly
# enabled, this binds to the original InMemoryJobRepository
# (storage/results/*.json) instead of MongoDB, so analysis jobs work on a
# machine with no reachable Atlas cluster. This is the ONLY repository
# affected -- responders/dispatch/incidents/audit-log stay MongoDB-only
# regardless of this flag, so a job's own persistence backend is always
# singular and never silently mixed between Mongo and JSON. Normal
# (non-demo) operation is completely unchanged: still MongoJobRepository,
# still requires a real MongoDB connection, exactly as before this flag
# existed.
_job_repository: JobRepository | None = None


def get_job_repository(settings: Settings = Depends(get_settings)) -> JobRepository:
    global _job_repository
    if _job_repository is None:
        if settings.LOCAL_DEMO_MODE:
            _job_repository = InMemoryJobRepository(results_dir=settings.RESULTS_DIR)
        else:
            _job_repository = MongoJobRepository(get_database())
    return _job_repository


def get_job_executor(
    background_tasks: BackgroundTasks,
    job_repository: JobRepository = Depends(get_job_repository),
) -> JobExecutor:
    def _run(job_id: str, video_path: Path, original_filename: str) -> None:
        run_analysis_job(job_id, video_path, original_filename, job_repository)

    return InProcessJobExecutor(background_tasks, _run)


def _validate_upload(file: UploadFile, settings: Settings) -> str:
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file has no filename.")

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
        allowed = ", ".join(settings.ALLOWED_VIDEO_EXTENSIONS)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type '{ext}'. Allowed: {allowed}",
        )
    return ext


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_analysis(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    job_repository: JobRepository = Depends(get_job_repository),
    job_executor: JobExecutor = Depends(get_job_executor),
) -> dict:
    ext = _validate_upload(file, settings)

    job_id = str(uuid.uuid4())
    # Server-generated filename -- never trust the client-supplied name for
    # the on-disk path (prevents path traversal / collisions).
    dest_path = settings.UPLOAD_DIR / f"{job_id}{ext}"

    size = 0
    max_size = settings.max_upload_size_bytes
    with dest_path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_size:
                out.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
                )
            out.write(chunk)

    job = AnalysisResult(
        job_id=job_id,
        status=AnalysisStatus.QUEUED,
        filename=file.filename,
    )
    try:
        job_repository.create(job)
    except MongoDBUnavailableError:
        # The video was already written to dest_path above -- since job
        # tracking itself could not be persisted, there is no job for it to
        # belong to, so remove the orphaned upload rather than leak it on
        # every failed submission while the database is unreachable.
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The analysis job database is temporarily unavailable; this submission was not "
            "accepted and no job was created. The video was not retained. The inference "
            "pipeline and models are unaffected -- this is a persistence issue only.",
        )

    job_executor.submit(job_id, dest_path, file.filename)

    return {"job_id": job_id, "status": job.status}


@router.get("", response_model=list[AnalysisJobSummary])
def list_analysis_jobs(
    limit: int = 50,
    before: str | None = None,
    job_repository: JobRepository = Depends(get_job_repository),
) -> list[AnalysisJobSummary]:
    """Most-recently-started analysis jobs first, for the frontend's history/
    audit-trail view to reload on page load/refresh instead of starting
    empty. `before` is an ISO-8601 `started_at` cursor for pagination.
    Returns [] when no jobs exist yet -- never fabricated rows."""
    try:
        jobs = job_repository.list(limit=limit, before=before)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The analysis job database is temporarily unavailable; job history cannot be read.",
        )
    return [
        AnalysisJobSummary(
            job_id=j.job_id,
            status=j.status,
            filename=j.filename,
            started_at=j.started_at,
            completed_at=j.completed_at,
            anomaly_detected=j.anomaly_detected,
            anomaly_probability=j.anomaly_probability,
            likely_action=j.likely_action,
            action_confidence=j.action_confidence,
            error=j.error,
        )
        for j in jobs
    ]


@router.get("/{job_id}", response_model=AnalysisResult)
def get_analysis_status(
    job_id: str,
    job_repository: JobRepository = Depends(get_job_repository),
) -> AnalysisResult:
    try:
        job = job_repository.get(job_id)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The analysis job database is temporarily unavailable; job status cannot be read.",
        )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job_id: {job_id}")
    return job


@router.get("/{job_id}/result", response_model=AnalysisResult)
def get_analysis_result(
    job_id: str,
    job_repository: JobRepository = Depends(get_job_repository),
) -> AnalysisResult:
    try:
        job = job_repository.get(job_id)
    except MongoDBUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The analysis job database is temporarily unavailable; the result cannot be read.",
        )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job_id: {job_id}")
    if job.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Job {job_id} is not completed yet (status={job.status}).",
        )
    return job
