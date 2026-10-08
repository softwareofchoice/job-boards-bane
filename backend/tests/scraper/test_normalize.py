from datetime import date, datetime

import pytest

from app.scraper.normalize import dedupe, parse_posted, within_days
from tests.scraper.helpers import posting

NOW = datetime(2026, 10, 8, 12, 0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3 days ago", date(2026, 10, 5)),
        ("30+ days ago", date(2026, 9, 8)),
        ("1 day ago", date(2026, 10, 7)),
        ("an hour ago", date(2026, 10, 8)),
        ("5 minutes ago", date(2026, 10, 8)),
        ("Just posted", date(2026, 10, 8)),
        ("Today", date(2026, 10, 8)),
        ("yesterday", date(2026, 10, 7)),
        ("2 weeks ago", date(2026, 9, 24)),
        ("a month ago", date(2026, 9, 8)),
        ("Full-time", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_posted(text: str | None, expected: date | None) -> None:
    assert parse_posted(text, NOW) == expected


def test_dedupe_keeps_longest_description_in_first_position() -> None:
    a = posting(title="Dev", company="Acme", description="short")
    b = posting(title="Other", company="Globex")
    a2 = posting(title=" dev ", company="ACME", description="a much longer description")
    c = posting(title="Dev", company="Acme", location="Remote")

    result = dedupe([a, b, a2, c])

    assert [p.company for p in result] == ["ACME", "Globex", "Acme"]
    assert result[0].description == "a much longer description"


def test_within_days_keeps_unknown_dates() -> None:
    today = date(2026, 10, 8)
    assert within_days(posting(posted_at=date(2026, 10, 1)), 7, today)
    assert not within_days(posting(posted_at=date(2026, 9, 30)), 7, today)
    assert within_days(posting(posted_at=None), 7, today)
