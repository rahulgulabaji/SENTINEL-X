"""Minimal incident persistence -- backs the dispatch workflow with a real
incident_id to reference, nothing more. No incident entity existed anywhere
in this codebase before this module; this is deliberately the smallest shape
that lets app/api/routes/dispatch.py persist a dispatch record against a
real incident reference instead of a loose job_id string.

An incident is auto-created (status "open") when analysis_service.py sees a
completed job with anomaly_detected=True -- but this NEVER sends an SMS or
triggers dispatch. Creating a reviewable record and sending an alert are
fully decoupled: dispatch send remains explicit-operator-action-only,
unconditionally, regardless of how many incidents exist.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.repositories.mongo_job_repository import MongoDBUnavailableError
from app.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentRepository:
    def __init__(self, db: Database):
        self._collection: Collection = db["incidents"]

    def create_from_job(self, job: AnalysisResult) -> dict:
        """Builds an incident document from an already-completed,
        already-persisted AnalysisResult. Uses only real values the
        pipeline already computed (anomaly_probability, likely_action,
        action_confidence) -- never generates or alters a prediction."""
        now = _utcnow_iso()
        incident = {
            "incident_id": str(uuid.uuid4()),
            "job_id": job.job_id,
            "status": "open",
            "anomaly_probability": job.anomaly_probability,
            "likely_action": job.likely_action,
            "action_confidence": job.action_confidence,
            "created_at": now,
            "updated_at": now,
        }
        try:
            self._collection.insert_one(dict(incident))
        except PyMongoError as exc:
            logger.error("Failed to create incident for job %s in MongoDB.", job.job_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not create incident for job {job.job_id}: database unavailable.") from exc
        return incident

    def list(self, *, status: str | None = None, limit: int = 50, before: str | None = None) -> list[dict]:
        query: dict = {}
        if status:
            query["status"] = status
        if before:
            query["created_at"] = {"$lt": before}
        try:
            cursor = (
                self._collection.find(query)
                .sort([("created_at", -1), ("_id", -1)])
                .limit(limit)
            )
            docs = list(cursor)
        except PyMongoError as exc:
            logger.error("Failed to list incidents from MongoDB.", exc_info=True)
            raise MongoDBUnavailableError("Could not list incidents: database unavailable.") from exc
        for doc in docs:
            doc.pop("_id", None)
        return docs

    def get(self, incident_id: str) -> dict | None:
        try:
            doc = self._collection.find_one({"incident_id": incident_id})
        except PyMongoError as exc:
            logger.error("Failed to read incident %s from MongoDB.", incident_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not read incident {incident_id}: database unavailable.") from exc
        if doc is None:
            return None
        doc.pop("_id", None)
        return doc

    def update_status(self, incident_id: str, status: str) -> dict | None:
        try:
            doc = self._collection.find_one_and_update(
                {"incident_id": incident_id},
                {"$set": {"status": status, "updated_at": _utcnow_iso()}},
                return_document=True,
            )
        except PyMongoError as exc:
            logger.error("Failed to update incident %s in MongoDB.", incident_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not update incident {incident_id}: database unavailable.") from exc
        if doc is None:
            return None
        doc.pop("_id", None)
        return doc

    def list_open(self) -> list[dict]:
        try:
            docs = list(self._collection.find({"status": "open"}))
        except PyMongoError as exc:
            logger.error("Failed to list open incidents from MongoDB.", exc_info=True)
            raise MongoDBUnavailableError("Could not list open incidents: database unavailable.") from exc
        for doc in docs:
            doc.pop("_id", None)
        return docs


_repository: IncidentRepository | None = None


def get_incident_repository(db: Database | None = None) -> IncidentRepository:
    global _repository
    if db is not None:
        return IncidentRepository(db)
    if _repository is None:
        from app.core.mongodb import get_database

        _repository = IncidentRepository(get_database())
    return _repository
