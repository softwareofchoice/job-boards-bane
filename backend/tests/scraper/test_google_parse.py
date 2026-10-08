from datetime import date, datetime
from pathlib import Path

import pytest

from app.scraper.sources.google_parse import (
    LayoutChangedError,
    is_blocked,
    merge,
    parse_detail,
    parse_list,
)

FIXTURES = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_list_reads_cards_and_skips_incomplete_ones() -> None:
    cards = parse_list(read("jobs_page.html"))
    assert len(cards) == 2
    first, second = cards
    assert first.title == "Senior Python Developer"
    assert first.company == "Acme Corp"
    assert first.location == "Austin, TX"
    assert first.via == "LinkedIn"
    assert first.posted_text == "3 days ago"
    assert first.salary_text == "$140K\u2013$170K a year"
    assert second.location == "Remote"
    assert second.posted_text == "30+ days ago"
    assert second.salary_text is None


def test_parse_detail() -> None:
    detail = parse_detail(read("jobs_page.html"))
    assert detail.description.splitlines() == [
        "We are looking for a Senior Python Developer.",
        "You will build APIs with FastAPI and PostgreSQL.",
        "5+ years of experience required.",
    ]
    assert detail.apply_urls[0].startswith("https://www.linkedin.com/jobs/view/123")
    assert len(detail.apply_urls) == 2
    assert detail.salary_text == "$140K\u2013$170K a year"


def test_merge_builds_a_posting() -> None:
    page = read("jobs_page.html")
    raw = merge(parse_list(page)[0], parse_detail(page), datetime(2026, 10, 8), "https://fallback")
    assert raw.posted_at == date(2026, 10, 5)
    assert raw.url.startswith("https://www.linkedin.com/")
    assert "FastAPI" in raw.description


def test_changed_layout_is_detected() -> None:
    page = read("changed_layout.html")
    with pytest.raises(LayoutChangedError):
        parse_list(page)
    with pytest.raises(LayoutChangedError):
        parse_detail(page)
    assert not is_blocked(page)


def test_captcha_is_detected() -> None:
    assert is_blocked(read("captcha.html"))
    assert is_blocked("<html></html>", url="https://www.google.com/sorry/index?continue=x")
    assert not is_blocked(read("jobs_page.html"), url="https://www.google.com/search?q=x")
