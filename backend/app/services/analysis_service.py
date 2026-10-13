"""
Orchestrates a single analysis job: this is the function the JobExecutor
actually runs in the background. Upload validation (extension/size checks,
safe filename generation) happens in the route before the executor is
invoked -- this function assumes it is handed an already-saved, valid video
file and only owns the "run inference and record the outcome" half.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.inference.final_demo_inference import get_pipeline
from app.repositories.audit_repository import get_audit_repository
from app.repositories.detection_event_repository import get_detection_event_repository
from app.repositories.incident_repository import get_incident_repository
from app.schemas.analysis import ActionCandidate, AnalysisStatus
from app.services.job_repository import JobRepository

logger = logging.getLogger(__name__)

# Belt-and-suspenders redaction for the one job-record field that stores a
# raw exception message (`error=`, below) and IS returned to API callers via
# GET /v1/analysis/{job_id}/result -- unlike audit_repository.py's
# error_category (always a short machine word, never free text), this field
# exists specifically to carry diagnostic detail, so it can't just be
# dropped; it has to be scrubbed instead.
#
# Matches any "scheme://[user[:pass]@]host[...]" URI and replaces the
# credential portion (and the user:pass@ separator) with "***". Covers
# mongodb://, mongodb+srv://, http(s)://, and any other scheme a future
# exception might happen to stringify, since the risk is "some library
# embedded a credential-bearing URL in its error text", not specifically
# MongoDB's own driver.
_CREDENTIAL_URI_PATTERN = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/\s@]+@)")

# Max length for the sanitized message. Long enough to keep a useful
# diagnostic (exception type + a real message), short enough that a huge
# stack-trace-shaped string (or a deliberately oversized exception message)
# can't bloat the stored job document or the API response.
_MAX_SANITIZED_ERROR_LENGTH = 300


def sanitize_error_message(exc: Exception, *, max_length: int = _MAX_SANITIZED_ERROR_LENGTH) -> str:
    """Turns a raw exception into a safe-to-store, safe-to-return string:
    the exception's own message with any embedded credential-bearing URI
    redacted and any literal configured secret value (MONGODB_URI,
    SMS_GATEWAY_PASSWORD) removed by exact match, then truncated to
    `max_length`. Keeps the exception's class name as a prefix so the
    diagnostic value (what kind of failure this was) survives even when the
    message itself gets heavily redacted or truncated.

    Never raises: sanitization failing is not a reason to lose the fact that
    the job itself failed, so any error constructing the safe string falls
    back to a fixed, info-free placeholder rather than propagating."""
    try:
        raw = str(exc)

        redacted = _CREDENTIAL_URI_PATTERN.sub(r"\1***@", raw)

        settings = get_settings()
        for secret in (settings.MONGODB_URI, settings.SMS_GATEWAY_PASSWORD):
            if secret:
                redacted = redacted.replace(secret, "***")

        safe = f"{type(exc).__name__}: {redacted}" if redacted else type(exc).__name__
        if len(safe) > max_length:
            safe = safe[: max_length - 3] + "..."
        return safe
    except Exception:
        logger.warning("sanitize_error_message itself failed; using a fixed placeholder.", exc_info=True)
        return "Internal error (details withheld)."


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

        updated_job = job_repository.update(
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
            model_window_diagnostics=output.model_window_diagnostics or [],
            model_detection_summary=output.model_detection_summary,
        )

        # Audit record logged only after the real COMPLETED update above has
        # actually returned a job -- never claims completion if persistence
        # of the result itself failed (updated_job is None, or the update()
        # call raised and we're already in the except branch below instead).
        if updated_job is not None:
            get_audit_repository().log(
                "analysis_job_completed",
                module="analysis",
                resource_type="analysis_job",
                resource_id=job_id,
                correlation_id=job_id,
                summary=f"Analysis job completed for '{original_filename}' "
                f"(anomaly_detected={updated_job.anomaly_detected}).",
                details={"anomaly_detected": updated_job.anomaly_detected},
            )

        # Additive persistence only -- no inference/calculation logic above
        # this point changes. Uses only the real values the pipeline just
        # computed (anomaly_detected, temporal_evidence, etc.); never
        # generates a new prediction. An incident is auto-created on a
        # detected anomaly, but this never sends an SMS and never triggers
        # any outbound alert -- record creation and operator-triggered
        # sending stay fully decoupled (see
        # app/repositories/incident_repository.py's module docstring).
        if updated_job is not None and updated_job.anomaly_detected:
            try:
                incident = get_incident_repository().create_from_job(updated_job)
                get_detection_event_repository().create_from_job(updated_job)
                get_audit_repository().log(
                    "incident_created",
                    module="incidents",
                    resource_type="incident",
                    resource_id=incident["incident_id"],
                    correlation_id=job_id,
                    summary=f"Incident auto-created from job {job_id} (status=open).",
                )
            except Exception:
                # A MongoDB outage here must not turn an otherwise-successful
                # analysis job into a FAILED one -- the job's own COMPLETED
                # result above has already been persisted (or the exception
                # from that persist already propagated past this point).
                logger.exception(
                    "Could not persist incident/detection-event records for job %s; "
                    "the analysis result itself was still recorded.",
                    job_id,
                )
                get_audit_repository().log(
                    "incident_creation_failed",
                    module="incidents",
                    resource_type="analysis_job",
                    resource_id=job_id,
                    correlation_id=job_id,
                    outcome="failure",
                    summary=f"Could not create incident/detection-events for job {job_id}.",
                    error_category="mongodb_unavailable",
                )
    except Exception as exc:
        # Full, unredacted exception goes to the server-side log only
        # (logger.exception below) -- never to the stored job record or any
        # API response. The job's own `error` field uses the sanitized
        # version, since that field is returned to callers via
        # GET /v1/analysis/{job_id}/result.
        logger.exception("Analysis job %s failed for %s", job_id, original_filename)
        job_repository.update(
            job_id,
            status=AnalysisStatus.FAILED,
            completed_at=datetime.now(timezone.utc),
            error=sanitize_error_message(exc),
        )
        get_audit_repository().log(
            "analysis_job_failed",
            module="analysis",
            resource_type="analysis_job",
            resource_id=job_id,
            correlation_id=job_id,
            outcome="failure",
            summary=f"Analysis job failed for '{original_filename}'.",
            error_category="inference_error",
        )
