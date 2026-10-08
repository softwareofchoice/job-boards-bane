"""One search run: collect, de-duplicate, score, rank (SCR-3, SCR-4). Runs as a background job."""

import logging
import threading
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.core.errors import AppError
from app.core.jobs import JobContext
from app.core.llm import LLM
from app.scraper.models import ScrapedPosting, ScrapeRun
from app.scraper.normalize import dedupe, within_days
from app.scraper.schemas import RawPosting, SearchOptions
from app.scraper.scorer import Weights, score_posting
from app.scraper.sources.base import JobSource

logger = logging.getLogger(__name__)

# SCR-3.6: one search at a time. Held from the API call that starts a run until it finishes.
RUN_LOCK = threading.Lock()


class SearchAlreadyRunningError(AppError):
    status_code = 409
    code = "search_running"


def rank_key(posting: ScrapedPosting) -> tuple[int, int]:
    """Highest score first; ties go to the most recent posting, unknown dates last (SCR-4.4)."""
    score = posting.score if posting.score is not None else -1
    posted = posting.posted_at.toordinal() if posting.posted_at else 0
    return (-score, -posted)


def apply_ranking(postings: list[ScrapedPosting], jobs_selected: int) -> None:
    scored = sorted((p for p in postings if p.score is not None), key=rank_key)
    for rank, posting in enumerate(scored, start=1):
        posting.rank = rank
        posting.selected = rank <= jobs_selected
    for posting in postings:
        if posting.score is None:  # SCR-4.6: never selected
            posting.rank = None
            posting.selected = False


def to_row(run_id: uuid.UUID, position: int, raw: RawPosting) -> ScrapedPosting:
    return ScrapedPosting(
        run_id=run_id,
        position=position,
        title=raw.title,
        company=raw.company,
        location=raw.location,
        url=raw.url,
        via=raw.via,
        salary_text=raw.salary_text,
        posted_text=raw.posted_text,
        posted_at=raw.posted_at,
        description=raw.description,
    )


async def run_search(
    ctx: JobContext,
    run_id: uuid.UUID,
    source: JobSource,
    llm: LLM,
    settings: Settings,
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        run = session.get(ScrapeRun, run_id)
        assert run is not None
        opts = SearchOptions.model_validate(run.options)

    limit = opts.jobs_pulled
    ctx.update_progress(step="collecting", done=0, total=limit)
    result = await source.search(
        opts, limit, lambda n: ctx.update_progress(step="collecting", done=n, total=limit)
    )
    today = datetime.now(UTC).date()
    raw = [p for p in dedupe(result.postings) if within_days(p, opts.days_since_posting, today)]
    raw = raw[:limit]

    with sessions() as session:
        run = session.get(ScrapeRun, run_id)
        assert run is not None
        run.stopped_reason = result.stopped_reason
        run.pulled_count = len(raw)
        session.add_all(to_row(run_id, i, p) for i, p in enumerate(raw))
        session.commit()

    weights = Weights.from_settings(settings)
    total = len(raw)
    ctx.update_progress(step="scoring", done=0, total=total)
    with sessions() as session:
        run = session.get(ScrapeRun, run_id)
        assert run is not None
        rows = sorted(run.postings, key=lambda p: p.position)
        for done, (row, posting) in enumerate(zip(rows, raw, strict=True), start=1):
            try:
                score = await score_posting(
                    llm, opts, posting, weights=weights, max_chars=settings.scorer_max_chars
                )
            except Exception as exc:  # SCR-4.6: one bad posting doesn't fail the run
                logger.warning("Scoring failed for %s at %s: %s", row.title, row.company, exc)
                row.score_error = str(exc) or type(exc).__name__
            else:
                row.score = score.overall
                row.sub_scores = score.sub_scores.model_dump()
                row.matched_skills = score.matched_skills
                row.missing_skills = score.missing_skills
                row.rationale = score.rationale
            session.commit()
            ctx.update_progress(step="scoring", done=done, total=total)

        apply_ranking(rows, opts.jobs_selected)
        session.commit()
    ctx.update_progress(step="done", done=total, total=total)
