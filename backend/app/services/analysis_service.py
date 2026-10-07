"""
Orchestrates a single analysis job: this is the function the JobExecutor
actually runs in the background. Upload validation (extension/size checks,
safe filename generation) happens in the route before the executor is
invoked -- this function assumes it is handed an already-saved, valid video
file and only owns the "run inference and record the outcome" half.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.inference.final_demo_inference import get_pipeline
from app.schemas.analysis import ActionCandidate, AnalysisStatus
from app.services.job_repository import JobRepository

logger = logging.getLogger(__name__)


def run_analysis_job(
    job_id: str,
    video_path: Path,
    original_filename: str,
    job_repository: JobRepository,
) -> None:
    job_repository.update(
        job_id,
        status=AnalysisStatus.PROCESSING,
        started_at=datetime.now(timezone.utc),
    )

    try:
        output = get_pipeline().analyze(str(video_path))

        job_repository.update(
            job_id,
            status=AnalysisStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            processing_time_seconds=output.elapsed_seconds,
            anomaly_detected=output.is_anomaly,
            anomaly_probability=output.anomaly_probability,
            likely_action=output.likely_action,
            action_confidence=output.action_confidence,
            action_candidates=[
                ActionCandidate(class_name=name, probability=prob)
                for name, prob in output.action_candidates
            ],
            temporal_evidence=output.temporal_evidence or {"available": False, "window_duration_seconds": 0.0, "windows": []},
        )
    except Exception as exc:
        logger.exception("Analysis job %s failed for %s", job_id, original_filename)
        job_repository.update(
            job_id,
            status=AnalysisStatus.FAILED,
            completed_at=datetime.now(timezone.utc),
            error=str(exc),
        )
