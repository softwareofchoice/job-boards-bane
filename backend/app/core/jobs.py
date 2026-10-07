"""Background jobs: work that takes minutes runs outside the request and reports progress."""

import asyncio
import inspect
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import NotFoundError
from app.core.models import Job, JobStatus

logger = logging.getLogger(__name__)

INTERRUPTED = "interrupted"


class JobContext:
    """Handed to a job's function so it can report progress."""

    def __init__(self, job_id: uuid.UUID, sessions: sessionmaker[Session]) -> None:
        self.job_id = job_id
        self._sessions = sessions

    def update_progress(self, **progress: Any) -> None:
        """Replace the job's progress, e.g. `update_progress(step="scoring", done=3, total=40)`."""
        with self._sessions() as session:
            session.execute(update(Job).where(Job.id == self.job_id).values(progress=progress))
            session.commit()


JobFn = Callable[[JobContext], Awaitable[None] | None]


def create_job(session: Session, kind: str) -> Job:
    job = Job(kind=kind, status=JobStatus.QUEUED, progress={})
    session.add(job)
    session.commit()
    return job


def get_job(session: Session, job_id: uuid.UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found.")
    return job


def run_job(job_id: uuid.UUID, fn: JobFn, sessions: sessionmaker[Session]) -> None:
    """Run `fn` and record the outcome. Meant for FastAPI BackgroundTasks.

    This is a plain function, so BackgroundTasks runs it in a worker thread; an async `fn`
    gets its own event loop there and doesn't block the server's.
    """
    _set_status(sessions, job_id, JobStatus.RUNNING)
    try:
        result = fn(JobContext(job_id, sessions))
        if inspect.isawaitable(result):
            asyncio.run(_await(result))
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        _set_status(sessions, job_id, JobStatus.FAILED, error=str(exc) or type(exc).__name__)
        return
    _set_status(sessions, job_id, JobStatus.SUCCEEDED)


async def _await(result: Awaitable[None]) -> None:
    await result


def fail_interrupted_jobs(session: Session) -> int:
    """At startup, jobs still queued or running were cut off by a restart: mark them failed."""
    result = session.execute(
        update(Job)
        .where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
        .values(status=JobStatus.FAILED, error=INTERRUPTED, finished_at=datetime.now(UTC))
    )
    session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def _set_status(
    sessions: sessionmaker[Session], job_id: uuid.UUID, status: JobStatus, error: str | None = None
) -> None:
    values: dict[str, Any] = {"status": status, "error": error}
    if status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
        values["finished_at"] = datetime.now(UTC)
    with sessions() as session:
        session.execute(update(Job).where(Job.id == job_id).values(**values))
        session.commit()
