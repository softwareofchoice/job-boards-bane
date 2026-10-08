from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.scraper.sources.base import JobSourceError
from app.scraper.sources.serpapi import SerpApiSource
from tests.scraper.helpers import options


def job(i: int, **overrides: Any) -> dict[str, Any]:
    """Shaped like an item of SerpAPI's google_jobs `jobs_results`."""
    item: dict[str, Any] = {
        "title": f"Python Developer {i}",
        "company_name": f"Company {i}",
        "location": "Austin, TX",
        "via": "LinkedIn",
        "description": f"Description {i}",
        "detected_extensions": {"posted_at": "2 days ago", "salary": "120K\u2013150K a year"},
        "apply_options": [{"title": "LinkedIn", "link": f"https://linkedin.example/{i}"}],
        "share_link": f"https://www.google.com/search?ibp=htl;jobs&q={i}",
    }
    item.update(overrides)
    return item


def make_source(
    pages: list[dict[str, Any] | httpx.Response],
) -> tuple[SerpApiSource, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = pages[len(requests) - 1]
        return page if isinstance(page, httpx.Response) else httpx.Response(200, json=page)

    return SerpApiSource("key123", transport=httpx.MockTransport(handler)), requests


async def test_maps_results_and_follows_pagination() -> None:
    src, requests = make_source(
        [
            {"jobs_results": [job(1), job(2)], "serpapi_pagination": {"next_page_token": "tok"}},
            {"jobs_results": [job(3, via="via Indeed", apply_options=[])]},
        ]
    )
    result = await src.search(options(), 10, lambda n: None)

    assert [p.title for p in result.postings] == [f"Python Developer {i}" for i in (1, 2, 3)]
    assert result.stopped_reason == "exhausted"
    first = result.postings[0]
    assert first.company == "Company 1"
    assert first.via == "LinkedIn"
    assert first.url == "https://linkedin.example/1"
    assert first.salary_text == "120K\u2013150K a year"
    assert first.posted_at == datetime.now(UTC).date() - timedelta(days=2)
    assert result.postings[2].via == "Indeed"
    assert result.postings[2].url.startswith("https://www.google.com/search")

    params = requests[0].url.params
    assert params["engine"] == "google_jobs"
    assert params["q"] == '"Python Developer" jobs near Austin, TX'
    assert params["api_key"] == "key123"
    assert requests[1].url.params["next_page_token"] == "tok"


async def test_stops_at_limit() -> None:
    src, requests = make_source(
        [
            {
                "jobs_results": [job(i) for i in range(10)],
                "serpapi_pagination": {"next_page_token": "t"},
            },
        ]
    )
    result = await src.search(options(), 4, lambda n: None)
    assert len(result.postings) == 4
    assert result.stopped_reason is None
    assert len(requests) == 1


async def test_rate_limit_keeps_partial_results() -> None:
    src, _ = make_source(
        [
            {"jobs_results": [job(1)], "serpapi_pagination": {"next_page_token": "t"}},
            httpx.Response(429, json={"error": "rate limited"}),
        ]
    )
    result = await src.search(options(), 10, lambda n: None)
    assert len(result.postings) == 1
    assert result.stopped_reason == "blocked"


async def test_api_error_on_first_page_is_raised() -> None:
    src, _ = make_source([httpx.Response(401, json={"error": "Invalid API key."})])
    with pytest.raises(JobSourceError, match="Invalid API key"):
        await src.search(options(), 10, lambda n: None)


async def test_no_results_is_not_an_error() -> None:
    src, _ = make_source([{"error": "Google hasn't returned any results for this query."}])
    result = await src.search(options(), 10, lambda n: None)
    assert result.postings == []
    assert result.stopped_reason == "exhausted"


async def test_missing_key() -> None:
    with pytest.raises(JobSourceError, match="SERPAPI_KEY"):
        await SerpApiSource(None).search(options(), 10, lambda n: None)
