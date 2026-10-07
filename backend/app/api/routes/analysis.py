"""Analysis API routes: submit a video for analysis, check job status, and
fetch the completed result."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.schemas.analysis import AnalysisResult, AnalysisStatus
from app.services.analysis_service import run_analysis_job
from app.services.job_executor import InProcessJobExecutor, JobExecutor
from app.services.job_repository import InMemoryJobRepository, JobRepository

router = APIRouter(prefix="/v1/analysis", tags=["Analysis"])

# Single process-wide repository instance. This is the one concrete binding
# in the app: everywhere else depends on the JobRepository/JobExecutor
# abstractions, not on these classes directly.
_job_repository = InMemoryJobRepository(results_dir=get_settings().RESULTS_DIR)


def get_job_repository() -> JobRepository:
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
    job_repository.create(job)

    job_executor.submit(job_id, dest_path, file.filename)

    return {"job_id": job_id, "status": job.status}


@router.get("/{job_id}", response_model=AnalysisResult)
def get_analysis_status(
    job_id: str,
    job_repository: JobRepository = Depends(get_job_repository),
) -> AnalysisResult:
    job = job_repository.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job_id: {job_id}")
    return job


@router.get("/{job_id}/result", response_model=AnalysisResult)
def get_analysis_result(
    job_id: str,
    job_repository: JobRepository = Depends(get_job_repository),
) -> AnalysisResult:
    job = job_repository.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job_id: {job_id}")
    if job.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Job {job_id} is not completed yet (status={job.status}).",
        )
    return job
