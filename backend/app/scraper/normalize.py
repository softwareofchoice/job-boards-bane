"""Turning raw source data into clean postings: dates, de-duplication (SCR-3.2, SCR-3.3)."""

import re
from datetime import date, datetime, timedelta

from app.scraper.schemas import RawPosting

_RELATIVE = re.compile(
    r"(?P<n>\d+|an?|one)\+?\s*(?P<unit>minute|min|hour|hr|day|week|wk|month|mo)s?\s+ago",
    re.IGNORECASE,
)
_UNIT_DAYS = {
    "minute": 0,
    "min": 0,
    "hour": 0,
    "hr": 0,
    "day": 1,
    "week": 7,
    "wk": 7,
    "month": 30,
    "mo": 30,
}


def parse_posted(text: str | None, now: datetime) -> date | None:
    """Turn "3 days ago", "30+ days ago", "an hour ago", "Just posted" etc. into a date.

    Returns None when the text can't be read; such postings are kept and shown as "unknown".
    """
    if not text:
        return None
    lowered = text.strip().lower()
    if lowered in {"just posted", "today", "just now", "new"}:
        return now.date()
    if lowered == "yesterday":
        return now.date() - timedelta(days=1)
    match = _RELATIVE.search(lowered)
    if not match:
        return None
    raw_n = match.group("n").lower()
    n = 1 if raw_n in {"a", "an", "one"} else int(raw_n)
    return now.date() - timedelta(days=n * _UNIT_DAYS[match.group("unit").lower()])


def _key(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def dedupe_key(posting: RawPosting) -> str:
    return f"{_key(posting.title)}|{_key(posting.company)}|{_key(posting.location)}"


def dedupe(postings: list[RawPosting]) -> list[RawPosting]:
    """Keep one posting per title + company + location: the one with the longest description.

    The order of first appearance is kept.
    """
    best: dict[str, RawPosting] = {}
    order: list[str] = []
    for posting in postings:
        key = dedupe_key(posting)
        if key not in best:
            order.append(key)
            best[key] = posting
        elif len(posting.description) > len(best[key].description):
            best[key] = posting
    return [best[k] for k in order]


def within_days(posting: RawPosting, days: int, today: date) -> bool:
    """Postings with an unknown date are kept (shown as "unknown")."""
    return posting.posted_at is None or (today - posting.posted_at).days <= days
