import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import get_sessionmaker
from app.core.jobs import INTERRUPTED, JobContext, create_job, fail_interrupted_jobs, run_job
from app.core.models import Job, JobStatus


def reload(session: Session, job_id: uuid.UUID) -> Job:
    session.expire_all()
    job = session.get(Job, job_id)
    assert job is not None
    return job


def test_successful_job_records_progress(session: Session) -> None:
    job = create_job(session, "dummy")
    seen_status: list[str] = []

    def work(ctx: JobContext) -> None:
        seen_status.append(reload(session, ctx.job_id).status)
        ctx.update_progress(step="counting", done=2, total=2)

    run_job(job.id, work, get_sessionmaker())

    job = reload(session, job.id)
    assert seen_status == [JobStatus.RUNNING]
    assert job.status == JobStatus.SUCCEEDED
    assert job.progress == {"step": "counting", "done": 2, "total": 2}
    assert job.error is None
    assert job.finished_at is not None


def test_async_job_runs(session: Session) -> None:
    job = create_job(session, "dummy")

    async def work(ctx: JobContext) -> None:
        await asyncio.sleep(0)
        ctx.update_progress(step="done")

    run_job(job.id, work, get_sessionmaker())
    assert reload(session, job.id).status == JobStatus.SUCCEEDED


def test_failing_job_records_error(session: Session) -> None:
    job = create_job(session, "dummy")

    def work(ctx: JobContext) -> None:
        raise ValueError("bad input")

    run_job(job.id, work, get_sessionmaker())

    job = reload(session, job.id)
    assert job.status == JobStatus.FAILED
    assert job.error == "bad input"
    assert job.finished_at is not None


def test_interrupted_jobs_are_failed_at_startup(session: Session) -> None:
    queued = create_job(session, "dummy")
    running = create_job(session, "dummy")
    running.status = JobStatus.RUNNING
    done = create_job(session, "dummy")
    done.status = JobStatus.SUCCEEDED
    session.commit()

    assert fail_interrupted_jobs(session) == 2

    for job_id in (queued.id, running.id):
        job = reload(session, job_id)
        assert job.status == JobStatus.FAILED
        assert job.error == INTERRUPTED
    assert reload(session, done.id).status == JobStatus.SUCCEEDED


def test_get_job_endpoint(client: TestClient, session: Session) -> None:
    job = create_job(session, "scrape")
    response = client.get(f"/api/jobs/{job.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(job.id)
    assert body["kind"] == "scrape"
    assert body["status"] == "queued"
    assert body["progress"] == {}

    assert client.get(f"/api/jobs/{uuid.uuid4()}").status_code == 404
