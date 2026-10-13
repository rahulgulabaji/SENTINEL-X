"""Detection event persistence -- a queryable fan-out of a completed job's
temporal evidence windows, not a duplicate of analysis_jobs.

analysis_jobs holds the 1:1 job record (status machine, timing, the full
result). detection_events holds one document per
temporal_evidence.windows[] entry, written once at job completion and never
recomputed -- this lets anything querying "all detections in a time range"
avoid deserializing every job's full temporal_evidence blob. Only created
for jobs where anomaly_detected is True (no events for clean videos --
avoids noise). Uses only values the inference pipeline already computed;
never generates a new prediction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.repositories.mongo_job_repository import MongoDBUnavailableError
from app.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)


class DetectionEventRepository:
    def __init__(self, db: Database):
        self._collection: Collection = db["detection_events"]

    def create_from_job(self, job: AnalysisResult) -> list[dict]:
        if not job.anomaly_detected or not job.temporal_evidence.available:
            return []
        now = datetime.now(timezone.utc).isoformat()
        events = []
        for window in job.temporal_evidence.windows:
            events.append(
                {
                    "job_id": job.job_id,
                    "window_index": window.window_index,
                    "start_time_seconds": window.start_time_seconds,
                    "end_time_seconds": window.end_time_seconds,
                    "stage1_attention": window.stage1_attention,
                    "stage2_attention": getattr(window, "stage2_attention", None),
                    "likely_action": job.likely_action,
                    "action_confidence": job.action_confidence,
                    "anomaly_detected": job.anomaly_detected,
                    "created_at": now,
                }
            )
        if not events:
            return []
        try:
            self._collection.insert_many([dict(e) for e in events])
        except PyMongoError as exc:
            logger.error("Failed to create detection events for job %s in MongoDB.", job.job_id, exc_info=True)
            raise MongoDBUnavailableError(
                f"Could not create detection events for job {job.job_id}: database unavailable."
            ) from exc
        return events

    def list_for_job(self, job_id: str) -> list[dict]:
        try:
            docs = list(self._collection.find({"job_id": job_id}))
        except PyMongoError as exc:
            logger.error("Failed to list detection events for job %s from MongoDB.", job_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not list detection events for job {job_id}: database unavailable.") from exc
        for doc in docs:
            doc.pop("_id", None)
        return docs


_repository: DetectionEventRepository | None = None


def get_detection_event_repository(db: Database | None = None) -> DetectionEventRepository:
    global _repository
    if db is not None:
        return DetectionEventRepository(db)
    if _repository is None:
        from app.core.mongodb import get_database

        _repository = DetectionEventRepository(get_database())
    return _repository
