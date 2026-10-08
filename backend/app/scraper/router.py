import re
import uuid
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_session, get_sessionmaker
from app.core.deps import get_llm
from app.core.errors import AppError, NotFoundError
from app.core.jobs import JobContext, create_job, run_job
from app.core.llm import LLM
from app.core.models import JobStatus
from app.scraper.csv_export import to_csv
from app.scraper.deps import get_job_source
from app.scraper.models import ScrapedPosting, ScrapeRun
from app.scraper.pipeline import RUN_LOCK, SearchAlreadyRunningError, run_search
from app.scraper.schemas import (
    PostingOut,
    RunDetail,
    RunStarted,
    RunSummary,
    SearchOptions,
    SubScores,
)
from app.scraper.sources.base import JobSource

router = APIRouter(prefix="/api/scraper", tags=["scraper"])

SessionDep = Annotated[Session, Depends(get_session)]


class RunInProgressError(AppError):
    status_code = 409
    code = "run_in_progress"


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
def start_run(
    opts: SearchOptions,
    session: SessionDep,
    background: BackgroundTasks,
    source: Annotated[JobSource, Depends(get_job_source)],
    llm: Annotated[LLM, Depends(get_llm)],
) -> RunStarted:
    """Start a search (SCR-1, SCR-3). Only one runs at a time (SCR-3.6)."""
    if not RUN_LOCK.acquire(blocking=False):
        raise SearchAlreadyRunningError("A search is already running. Wait for it to finish.")
    try:
        job = create_job(session, "scrape")
        run = ScrapeRun(
            job_id=job.id,
            options=opts.model_dump(mode="json"),
            source=source.name,
            model=llm.model,
        )
        session.add(run)
        session.commit()
    except BaseException:
        RUN_LOCK.release()
        raise

    run_id, settings, sessions = run.id, get_settings(), get_sessionmaker()

    async def work(ctx: JobContext) -> None:
        await run_search(ctx, run_id, source, llm, settings, sessions)

    def run_and_release() -> None:
        try:
            run_job(job.id, work, sessions)
        finally:
            RUN_LOCK.release()

    background.add_task(run_and_release)
    return RunStarted(run_id=run.id, job_id=job.id)


def _summary(run: ScrapeRun, selected_count: int) -> RunSummary:
    return RunSummary(
        id=run.id,
        job_id=run.job_id,
        options=SearchOptions.model_validate(run.options),
        source=run.source,
        status=run.job.status,
        stopped_reason=run.stopped_reason,
        pulled_count=run.pulled_count,
        selected_count=selected_count,
        created_at=run.created_at,
    )


def _posting_out(p: ScrapedPosting) -> PostingOut:
    return PostingOut(
        id=p.id,
        title=p.title,
        company=p.company,
        location=p.location,
        url=p.url,
        via=p.via,
        salary_text=p.salary_text,
        posted_text=p.posted_text,
        posted_at=p.posted_at,
        description=p.description,
        score=p.score,
        sub_scores=SubScores.model_validate(p.sub_scores) if p.sub_scores else None,
        matched_skills=list(p.matched_skills),
        missing_skills=list(p.missing_skills),
        rationale=p.rationale,
        score_error=p.score_error,
        rank=p.rank,
        selected=p.selected,
    )


def _get_run(session: Session, run_id: uuid.UUID) -> ScrapeRun:
    run = session.get(ScrapeRun, run_id)
    if run is None:
        raise NotFoundError("Search not found.")
    return run


@router.get("/runs")
def list_runs(session: SessionDep) -> list[RunSummary]:
    """Past searches, newest first (SCR-5.5)."""
    runs = session.scalars(select(ScrapeRun).order_by(ScrapeRun.created_at.desc())).all()
    return [_summary(r, sum(p.selected for p in r.postings)) for r in runs]


@router.get("/runs/{run_id}")
def get_run(
    run_id: uuid.UUID, session: SessionDep, all: Annotated[bool, Query()] = False
) -> RunDetail:
    """A run with its progress and postings: the top X, or all N with `all=true` (SCR-5)."""
    run = _get_run(session, run_id)
    postings = [p for p in run.postings if all or p.selected]
    summary = _summary(run, sum(p.selected for p in run.postings))
    return RunDetail(
        **summary.model_dump(),
        progress=run.job.progress,
        error=run.job.error,
        model=run.model,
        postings=[_posting_out(p) for p in postings],
    )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "search"


@router.get("/runs/{run_id}/export.csv")
def export_csv(
    run_id: uuid.UUID, session: SessionDep, all: Annotated[bool, Query()] = False
) -> Response:
    run = _get_run(session, run_id)
    postings = [p for p in run.postings if all or p.selected]
    opts = SearchOptions.model_validate(run.options)
    stamp = run.created_at.astimezone(UTC).strftime("%Y%m%d-%H%M")
    filename = f"jobs-{_slug(opts.job_title)}-{stamp}.csv"
    return Response(
        content=to_csv(postings).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(run_id: uuid.UUID, session: SessionDep) -> None:
    run = _get_run(session, run_id)
    if run.job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise RunInProgressError("This search is still running.")
    session.delete(run)
    session.commit()
