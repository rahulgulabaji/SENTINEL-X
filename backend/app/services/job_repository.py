"""
Job state storage.

JobRepository is an explicit abstraction (not just a concrete class) so the
storage mechanism can change later without touching callers. The only
implementation for this phase, InMemoryJobRepository, keeps a dict index for
fast lookups during the process lifetime and writes through to
storage/results/{job_id}.json on every create()/update() call, so a result
is on disk the moment it's known rather than only at completion.

This is explicitly swappable for a SQLite-backed JobRepository later without
changing the interface or any calling code. SQLite is NOT introduced now.
"""

from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)


class JobRepository(ABC):
    @abstractmethod
    def create(self, job: AnalysisResult) -> None: ...

    @abstractmethod
    def get(self, job_id: str) -> AnalysisResult | None: ...

    @abstractmethod
    def update(self, job_id: str, **fields) -> AnalysisResult | None:
        """Applies `fields` onto the stored job and persists it. Returns the
        updated record, or None if job_id is unknown."""
        ...


class InMemoryJobRepository(JobRepository):
    def __init__(self, results_dir: Path):
        self._results_dir = results_dir
        self._jobs: dict[str, AnalysisResult] = {}
        self._lock = threading.Lock()

    def create(self, job: AnalysisResult) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            self._persist(job)

    def get(self, job_id: str) -> AnalysisResult | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> AnalysisResult | None:
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is None:
                return None
            updated = existing.model_copy(update=fields)
            self._jobs[job_id] = updated
            self._persist(updated)
            return updated

    def _persist(self, job: AnalysisResult) -> None:
        path = self._results_dir / f"{job.job_id}.json"
        try:
            path.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        except OSError:
            logger.exception("Failed to persist job result to %s", path)

    # TODO(startup-rehydrate): call this from the FastAPI lifespan on startup
    # to rebuild the in-memory index from previously persisted JSON results,
    # so job state survives a process restart. Not called yet -- in-memory
    # state is currently lost on restart even though the JSON files remain
    # on disk. Left as a documented extension point for this phase.
    def rebuild_from_disk(self) -> None:
        for path in self._results_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                job = AnalysisResult.model_validate(data)
                self._jobs[job.job_id] = job
            except (OSError, ValueError):
                logger.exception("Failed to rehydrate job from %s", path)
