"""Google Jobs results through SerpAPI's `google_jobs` engine (a licensed alternative, Q-4).

Note: this sends the search terms (never resumes) to SerpAPI.
"""

from datetime import UTC, datetime
from typing import Any

import httpx

from app.scraper.normalize import parse_posted
from app.scraper.schemas import RawPosting, SearchOptions, SourceResult
from app.scraper.sources.base import JobSourceError, ProgressFn, build_query

SERPAPI_URL = "https://serpapi.com/search.json"
MAX_PAGES = 15  # 10 results a page; enough for the 100-posting limit plus duplicates


class SerpApiSource:
    name = "serpapi"

    def __init__(
        self,
        api_key: str | None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: float = 30,
    ) -> None:
        self.api_key = api_key
        self._transport = transport
        self._timeout_s = timeout_s

    async def search(
        self, opts: SearchOptions, limit: int, on_progress: ProgressFn
    ) -> SourceResult:
        if not self.api_key:
            raise JobSourceError("Set SERPAPI_KEY to use the SerpAPI job source.")
        now = datetime.now(UTC)
        postings: list[RawPosting] = []
        params: dict[str, str] = {
            "engine": "google_jobs",
            "q": build_query(opts),
            "hl": "en",
            "api_key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
            for _ in range(MAX_PAGES):
                try:
                    response = await client.get(SERPAPI_URL, params=params)
                except httpx.TransportError as exc:
                    raise JobSourceError(f"Couldn't reach SerpAPI: {type(exc).__name__}") from exc
                if response.status_code == 429:
                    return SourceResult(postings=postings, stopped_reason="blocked")
                body: dict[str, Any] = response.json() if response.content else {}
                if response.is_error or "error" in body:
                    message = str(body.get("error", f"HTTP {response.status_code}"))
                    if "hasn't returned any results" in message:
                        break
                    if not postings:
                        raise JobSourceError(f"SerpAPI error: {message}")
                    return SourceResult(postings=postings, stopped_reason="blocked")
                for item in body.get("jobs_results", []):
                    postings.append(to_posting(item, now))
                    on_progress(len(postings))
                    if len(postings) >= limit:
                        return SourceResult(postings=postings)
                token = (body.get("serpapi_pagination") or {}).get("next_page_token")
                if not token:
                    break
                params["next_page_token"] = token
        return SourceResult(postings=postings, stopped_reason="exhausted")


def to_posting(item: dict[str, Any], now: datetime) -> RawPosting:
    ext = item.get("detected_extensions") or {}
    options = item.get("apply_options") or []
    url = (options[0].get("link") if options else None) or item.get("share_link") or ""
    via = item.get("via")
    if isinstance(via, str) and via.lower().startswith("via "):
        via = via[4:]
    posted_text = ext.get("posted_at")
    return RawPosting(
        title=str(item.get("title", "")).strip(),
        company=str(item.get("company_name", "")).strip(),
        location=(item.get("location") or None),
        posted_text=posted_text,
        posted_at=parse_posted(posted_text, now),
        url=url,
        via=via,
        salary_text=ext.get("salary"),
        description=str(item.get("description", "")),
    )
