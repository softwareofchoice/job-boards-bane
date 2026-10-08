from collections.abc import Callable
from typing import Protocol

from app.core.errors import AppError
from app.scraper.schemas import SearchOptions, SourceResult

ProgressFn = Callable[[int], None]


class JobSourceError(AppError):
    """The source can't be used at all (e.g. no API key). Partial results use stopped_reason."""

    status_code = 503
    code = "job_source_error"


class JobSource(Protocol):
    name: str

    async def search(
        self, opts: SearchOptions, limit: int, on_progress: ProgressFn
    ) -> SourceResult:
        """Collect up to `limit` postings. Report the count found so far via `on_progress`."""
        ...


def build_query(opts: SearchOptions) -> str:
    query = f'"{opts.job_title}" jobs'
    if opts.location:
        query += f" near {opts.location}"
    return query


def date_chip(days: int) -> str:
    """Google's closest "date posted" filter that still includes `days` (SCR-3.1).

    Results are filtered exactly on the parsed date afterwards.
    """
    if days <= 1:
        return "today"
    if days <= 3:
        return "3days"
    if days <= 7:
        return "week"
    return "month"
