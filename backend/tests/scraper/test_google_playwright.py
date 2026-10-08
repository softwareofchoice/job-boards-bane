"""Drives a real Chromium against local fixture pages that mimic Google's jobs view.

Needs a Playwright Chromium (`make scraper-browser`, or SCRAPER_CHROMIUM_PATH). Skipped when
none can be started, unless REQUIRE_BROWSER=1 (as in CI), which turns that into a failure.
"""

import asyncio
import functools
import os
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.scraper.sources.base import JobSourceError
from app.scraper.sources.google_playwright import GooglePlaywrightSource
from tests.scraper.helpers import options

FIXTURES = Path(__file__).parent / "fixtures"
CHROMIUM = os.environ.get("SCRAPER_CHROMIUM_PATH") or None


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def fixture_server() -> Iterator[str]:
    handler = functools.partial(QuietHandler, directory=str(FIXTURES))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module", autouse=True)
def browser_available() -> None:
    async def probe() -> None:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=CHROMIUM)
            await browser.close()

    try:
        asyncio.run(probe())
    except Exception as exc:
        if os.environ.get("REQUIRE_BROWSER") == "1":
            raise
        pytest.skip(f"No Playwright Chromium available: {exc}")


def source(base_url: str) -> GooglePlaywrightSource:
    return GooglePlaywrightSource(
        base_url=base_url, delay_s=0.1, chromium_path=CHROMIUM, wait_timeout_ms=3000
    )


async def test_collects_postings_and_loads_more_on_scroll(fixture_server: str) -> None:
    progress: list[int] = []
    result = await source(f"{fixture_server}/jobs_interactive.html").search(
        options(), 100, progress.append
    )

    assert [p.company for p in result.postings] == [
        "Acme",
        "Globex",
        "Initech",
        "Umbrella",
        "Hooli",
        "Wonka",
        "Tyrell",
    ]
    assert result.stopped_reason == "exhausted"
    first = result.postings[0]
    assert first.title == "Python Developer"
    assert first.location == "Austin, TX"
    assert first.via == "LinkedIn"
    assert first.posted_text == "2 days ago"
    assert first.url == "https://jobs.example.test/0"
    # The "Show full description" button was clicked.
    assert (
        first.description
        == "Python Developer at Acme. You will use Python, FastAPI and PostgreSQL."
    )
    assert result.postings[4].description.startswith("Senior Python Developer at Hooli")
    assert progress == list(range(1, 8))


async def test_stops_at_the_limit(fixture_server: str) -> None:
    result = await source(f"{fixture_server}/jobs_interactive.html").search(
        options(), 2, lambda n: None
    )
    assert len(result.postings) == 2
    assert result.stopped_reason is None


async def test_captcha_page_stops_as_blocked(fixture_server: str) -> None:
    result = await source(f"{fixture_server}/captcha.html").search(options(), 5, lambda n: None)
    assert result.postings == []
    assert result.stopped_reason == "blocked"


async def test_unknown_layout_stops_as_layout_changed(fixture_server: str) -> None:
    result = await source(f"{fixture_server}/changed_layout.html").search(
        options(), 5, lambda n: None
    )
    assert result.postings == []
    assert result.stopped_reason == "layout_changed"


def test_search_url_has_query_and_date_filter() -> None:
    url = source("https://www.google.com/search").search_url(options(days_since_posting=3))
    assert "q=%22Python+Developer%22+jobs+near+Austin%2C+TX" in url
    assert "ibp=htl%3Bjobs" in url
    assert "htichips=date_posted%3A3days" in url


async def test_missing_browser_gives_a_clear_error(fixture_server: str) -> None:
    bad = GooglePlaywrightSource(base_url=fixture_server, chromium_path="/nonexistent/chrome")
    with pytest.raises(JobSourceError, match="make scraper-browser"):
        await bad.search(options(), 1, lambda n: None)


async def test_unreachable_site_gives_a_clear_error() -> None:
    unreachable = source("http://127.0.0.1:1/search")
    with pytest.raises(JobSourceError, match="Couldn't load Google's job search"):
        await unreachable.search(options(), 1, lambda n: None)
