"""MongoDB-backed implementation of the existing JobRepository ABC.

Deliberately named mongo_job_repository.py, not job_repository.py -- the
latter name is already taken by app/services/job_repository.py (the
in-memory/JSON implementation plus the JobRepository ABC itself). Having
app/repositories/job_repository.py and app/services/job_repository.py as
distinct modules with the same basename would be an avoidable import
foot-gun; this module imports and subclasses the existing ABC unchanged
rather than redefining or moving it, so
`from app.services.job_repository import JobRepository` keeps working
everywhere it's already used (app/api/routes/analysis.py,
app/services/analysis_service.py).

Persists AnalysisResult documents to the `analysis_jobs` collection. Never
stores video binaries -- AnalysisResult itself only ever carries metadata/
results (filename, status, timing, model output); the actual video stays in
storage/uploads untouched by this module.
"""

from __future__ import annotations

import logging

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.schemas.analysis import AnalysisResult
from app.services.job_repository import JobRepository

logger = logging.getLogger(__name__)


class MongoDBUnavailableError(RuntimeError):
    """Raised when a persistent-data operation cannot reach MongoDB. Never
    caught and silently converted into a fake/empty result anywhere in this
    codebase -- callers (routes) must let this propagate into a truthful
    5xx rather than pretend the operation succeeded or that no data exists."""


class MongoJobRepository(JobRepository):
    """Same ABC, same semantics as InMemoryJobRepository (which remains
    untouched as a migration source / fallback-for-tests implementation) --
    only the storage backend differs."""

    def __init__(self, db: Database):
        self._collection: Collection = db["analysis_jobs"]

    def create(self, job: AnalysisResult) -> None:
        try:
            self._collection.insert_one(job.model_dump(mode="json"))
        except PyMongoError as exc:
            logger.error("Failed to persist analysis job %s to MongoDB.", job.job_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not persist job {job.job_id}: database unavailable.") from exc

    def get(self, job_id: str) -> AnalysisResult | None:
        try:
            doc = self._collection.find_one({"job_id": job_id})
        except PyMongoError as exc:
            logger.error("Failed to read analysis job %s from MongoDB.", job_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not read job {job_id}: database unavailable.") from exc
        if doc is None:
            return None
        doc.pop("_id", None)
        return AnalysisResult.model_validate(doc)

    def update(self, job_id: str, **fields) -> AnalysisResult | None:
        # model_dump(mode="json") on a throwaway validated instance would be
        # the "proper" way to re-serialize arbitrary field values the same
        # way AnalysisResult itself would, but update() receives raw Python
        # values (datetimes, nested Pydantic models like TemporalEvidence,
        # and lists of models like list[ActionCandidate]) directly from
        # analysis_service.py -- mirror InMemoryJobRepository's own approach
        # of using Pydantic's own JSON-mode serialization on each value only
        # where needed, passing through plain values (str/float/bool/None)
        # as-is. Also recurses into list/tuple values so a list of
        # BaseModel instances (e.g. action_candidates) is serialized
        # per-item instead of raising bson.errors.InvalidDocument.
        def _serialize(value):
            if hasattr(value, "model_dump"):
                return value.model_dump(mode="json")
            if isinstance(value, (list, tuple)):
                return [_serialize(item) for item in value]
            return value

        update_doc = {key: _serialize(value) for key, value in fields.items()}
        try:
            doc = self._collection.find_one_and_update(
                {"job_id": job_id},
                {"$set": update_doc},
                return_document=True,
            )
        except PyMongoError as exc:
            logger.error("Failed to update analysis job %s in MongoDB.", job_id, exc_info=True)
            raise MongoDBUnavailableError(f"Could not update job {job_id}: database unavailable.") from exc
        if doc is None:
            return None
        doc.pop("_id", None)
        return AnalysisResult.model_validate(doc)

    def list(self, *, limit: int = 50, before: str | None = None) -> list[AnalysisResult]:
        query: dict = {}
        if before:
            query["started_at"] = {"$lt": before}
        try:
            cursor = (
                self._collection.find(query)
                .sort([("started_at", -1), ("_id", -1)])
                .limit(limit)
            )
            docs = list(cursor)
        except PyMongoError as exc:
            logger.error("Failed to list analysis jobs from MongoDB.", exc_info=True)
            raise MongoDBUnavailableError("Could not list analysis jobs: database unavailable.") from exc
        results = []
        for doc in docs:
            doc.pop("_id", None)
            try:
                results.append(AnalysisResult.model_validate(doc))
            except Exception:
                logger.exception("Skipping malformed analysis job document: job_id=%r", doc.get("job_id"))
        return results
