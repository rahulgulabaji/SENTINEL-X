"""YOLO26 supporting-vision-layer API routes: health/model info, detect/track
job submission, job status/result polling, and single-track lookup.

Mirrors app/api/routes/analysis.py's structure and conventions exactly
(same upload-validation pattern, same safe-filename generation, same
status/result split, same Depends()-based wiring onto JobRepository/
JobExecutor) -- additive, registered alongside the existing routers in
main.py, never replacing them.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.inference.yolo26_service import get_yolo_service
from app.schemas.yolo import Line, YoloJobResult, YoloJobStatus, Zone
from app.services.job_executor import InProcessJobExecutor, JobExecutor
from app.services.job_repository import InMemoryJobRepository, JobRepository
from app.services.yolo_job_service import run_yolo_job

router = APIRouter(prefix="/v1/yolo", tags=["YOLO26"])

# Separate JobRepository instance from the analysis pipeline's, same class,
# different results_dir -- reuses the existing abstraction verbatim rather
# than forking a second job-tracking system (see app/services/job_repository.py).
_job_repository = InMemoryJobRepository(results_dir=get_settings().YOLO_RESULTS_DIR)


def get_yolo_job_repository() -> JobRepository:
    return _job_repository


def _make_yolo_job_executor(
    background_tasks: BackgroundTasks,
    job_repository: JobRepository,
    mode: str,
    zones: list[Zone],
    lines: list[Line],
) -> JobExecutor:
    """Builds a JobExecutor bound to this specific job's mode/zones/lines.

    JobExecutor.submit() has a fixed 3-arg interface (job_id, video_path,
    original_filename) shared with the untouched analysis pipeline -- it is
    not changed here. Instead, mode/zones/lines are closed over at
    construction time, before the executor is handed to the route, so the
    _run callable itself matches that interface exactly.
    """

    def _run(job_id: str, video_path: Path, original_filename: str) -> None:
        run_yolo_job(job_id, video_path, original_filename, mode, zones, lines, job_repository)

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


def _parse_zones(raw: str | None) -> list[Zone]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [Zone.model_validate(z) for z in data]
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid zones JSON: {exc}") from exc


def _parse_lines(raw: str | None) -> list[Line]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [Line.model_validate(l) for l in data]
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid lines JSON: {exc}") from exc


async def _save_upload(file: UploadFile, settings: Settings, job_id: str, ext: str) -> Path:
    dest_path = settings.YOLO_UPLOAD_DIR / f"{job_id}{ext}"
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
    return dest_path


def _submit_job(job_id: str, status_: YoloJobStatus, mode: str) -> YoloJobResult:
    return YoloJobResult(job_id=job_id, status=status_, mode=mode)


@router.get("/health")
def yolo_health() -> dict:
    service = get_yolo_service()
    info = service.get_model_info() if service.is_ready() else {}
    return {
        "status": "ok" if service.is_ready() else "model_not_loaded",
        "model_loaded": service.is_ready(),
        "device": info.get("device"),
    }


@router.get("/model")
def yolo_model_info() -> dict:
    service = get_yolo_service()
    if not service.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "YOLO model is not loaded.")
    return service.get_model_info()


@router.post("/detect", status_code=status.HTTP_202_ACCEPTED)
async def submit_detect(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    zones: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    job_repository: JobRepository = Depends(get_yolo_job_repository),
) -> dict:
    service = get_yolo_service()
    if not service.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "YOLO model is not loaded.")

    ext = _validate_upload(file, settings)
    parsed_zones = _parse_zones(zones)

    job_id = str(uuid.uuid4())
    dest_path = await _save_upload(file, settings, job_id, ext)

    job = _submit_job(job_id, YoloJobStatus.QUEUED, mode="detect")
    job_repository.create(job)
    job_executor = _make_yolo_job_executor(
        background_tasks, job_repository, mode="detect", zones=parsed_zones, lines=[],
    )
    job_executor.submit(job_id, dest_path, file.filename)

    return {"job_id": job_id, "status": job.status}


@router.post("/track", status_code=status.HTTP_202_ACCEPTED)
async def submit_track(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    zones: str | None = Form(default=None),
    lines: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    job_repository: JobRepository = Depends(get_yolo_job_repository),
) -> dict:
    service = get_yolo_service()
    if not service.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "YOLO model is not loaded.")

    ext = _validate_upload(file, settings)
    parsed_zones = _parse_zones(zones)
    parsed_lines = _parse_lines(lines)

    job_id = str(uuid.uuid4())
    dest_path = await _save_upload(file, settings, job_id, ext)

    job = _submit_job(job_id, YoloJobStatus.QUEUED, mode="track")
    job_repository.create(job)
    job_executor = _make_yolo_job_executor(
        background_tasks, job_repository, mode="track", zones=parsed_zones, lines=parsed_lines,
    )
    job_executor.submit(job_id, dest_path, file.filename)

    return {"job_id": job_id, "status": job.status}


@router.get("/jobs/{job_id}", response_model=YoloJobResult)
def get_job_status(
    job_id: str,
    job_repository: JobRepository = Depends(get_yolo_job_repository),
) -> YoloJobResult:
    job = job_repository.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job_id: {job_id}")
    return job


@router.get("/jobs/{job_id}/result", response_model=YoloJobResult)
def get_job_result(
    job_id: str,
    job_repository: JobRepository = Depends(get_yolo_job_repository),
) -> YoloJobResult:
    job = job_repository.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job_id: {job_id}")
    if job.status != YoloJobStatus.COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Job {job_id} is not completed yet (status={job.status}).",
        )
    return job


@router.get("/tracks/{job_id}/{track_id}")
def get_track_detail(
    job_id: str,
    track_id: int,
    job_repository: JobRepository = Depends(get_yolo_job_repository),
) -> dict:
    job = job_repository.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job_id: {job_id}")
    if job.status != YoloJobStatus.COMPLETED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Job {job_id} is not completed yet (status={job.status}).",
        )
    for track in job.tracks:
        if track.track_id == track_id:
            return track.model_dump()
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown track_id {track_id} in job {job_id}")
