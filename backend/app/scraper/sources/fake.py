"""A job source with canned postings, for tests and for running the app without Google."""

from datetime import UTC, datetime, timedelta

from app.scraper.schemas import RawPosting, SearchOptions, SourceResult, StopReason
from app.scraper.sources.base import ProgressFn


class FakeJobSource:
    name = "fake"

    def __init__(
        self, postings: list[RawPosting] | None = None, stopped_reason: StopReason | None = None
    ) -> None:
        self.postings = postings
        self.stopped_reason = stopped_reason
        self.calls: list[tuple[SearchOptions, int]] = []

    async def search(
        self, opts: SearchOptions, limit: int, on_progress: ProgressFn
    ) -> SourceResult:
        self.calls.append((opts, limit))
        postings = (self.postings if self.postings is not None else sample_postings(opts))[:limit]
        for i in range(len(postings)):
            on_progress(i + 1)
        return SourceResult(postings=postings, stopped_reason=self.stopped_reason)


def sample_postings(opts: SearchOptions, count: int = 12) -> list[RawPosting]:
    """Plausible postings built from the search, with a spread of skill overlap."""
    today = datetime.now(UTC).date()
    companies = [
        "Acme",
        "Globex",
        "Initech",
        "Umbrella",
        "Hooli",
        "Stark Industries",
        "Wayne Enterprises",
        "Cyberdyne",
        "Soylent",
        "Wonka",
        "Tyrell",
        "Vandelay",
    ]
    postings = []
    for i in range(count):
        skills = opts.skills[: max(1, len(opts.skills) - i % (len(opts.skills) + 1))]
        postings.append(
            RawPosting(
                title=opts.job_title if i % 3 else f"Senior {opts.job_title}",
                company=companies[i % len(companies)],
                location=opts.location or "Remote",
                posted_at=today - timedelta(days=i % max(1, opts.days_since_posting)),
                posted_text=f"{i % max(1, opts.days_since_posting)} days ago",
                url=f"https://jobs.example.test/{i}",
                via="Example Jobs",
                salary_text="$120K-$150K a year" if i % 2 == 0 else None,
                description=(
                    f"We're hiring a {opts.job_title}. You'll work with {', '.join(skills)}. "
                    f"{opts.years_experience}+ years of experience preferred."
                ),
            )
        )
    return postings
