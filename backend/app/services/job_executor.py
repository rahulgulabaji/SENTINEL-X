"""
Job execution strategy.

JobExecutor is a named, replaceable boundary around how an analysis job
actually gets run. The only implementation for this phase,
InProcessJobExecutor, wraps FastAPI's BackgroundTasks: the request handler
returns immediately while analysis_service.run_analysis_job runs in the same
process, in a background thread managed by Starlette.

This is a single-process execution strategy, appropriate for single-user /
demo scale (as verified: ~44s CPU inference per video). It is NOT suitable
for concurrent multi-user load, where a worker queue (Celery, RQ) would be
needed instead. The extension point for that is this same JobExecutor
interface -- a future CeleryJobExecutor/RQJobExecutor can be swapped in via
the dependency binding in main.py without changing the route or service
layer. Celery/Redis are NOT introduced now.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks


class JobExecutor(ABC):
    @abstractmethod
    def submit(self, job_id: str, video_path: Path, original_filename: str) -> None: ...


class InProcessJobExecutor(JobExecutor):
    def __init__(self, background_tasks: BackgroundTasks, run_job: Callable[[str, Path, str], None]):
        self._background_tasks = background_tasks
        self._run_job = run_job

    def submit(self, job_id: str, video_path: Path, original_filename: str) -> None:
        self._background_tasks.add_task(self._run_job, job_id, video_path, original_filename)
