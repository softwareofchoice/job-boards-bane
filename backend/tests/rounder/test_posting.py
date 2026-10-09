import httpx
import pytest

from app.rounder.posting import PostingUnavailableError, fetch_posting
from tests.rounder.helpers import POSTING

URL = "https://jobs.example.test/backend-engineer"

ARTICLE = f"""<html><head><title>Backend Engineer - Initech</title></head><body>
<nav><a href="/">Home</a> <a href="/jobs">All jobs</a></nav>
<main><article><h1>Backend Engineer</h1><p>{POSTING}</p>
<p>We offer flexible hours, a learning budget and a friendly team.</p></article></main>
<footer>© Initech · Privacy · Cookies</footer></body></html>"""

EMPTY_SHELL = '<html><body><div id="root"></div><script src="/app.js"></script></body></html>'


def transport(status: int = 200, html: str = ARTICLE) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status, text=html))


async def test_the_main_text_is_extracted() -> None:
    text = await fetch_posting(URL, transport=transport())
    assert "Required: Python, PostgreSQL and Kubernetes" in text
    assert "Privacy" not in text


async def test_a_page_built_with_javascript_is_rendered_in_a_browser() -> None:
    rendered: list[str] = []

    async def render(url: str) -> str:
        rendered.append(url)
        return ARTICLE

    text = await fetch_posting(URL, transport=transport(html=EMPTY_SHELL), render=render)
    assert rendered == [URL]
    assert "Kubernetes" in text


async def test_too_little_text_asks_for_pasted_text() -> None:
    with pytest.raises(PostingUnavailableError, match="Paste the description"):
        await fetch_posting(URL, transport=transport(html=EMPTY_SHELL))


async def test_an_http_error_or_unreachable_host_is_unavailable() -> None:
    async def broken_render(url: str) -> str:
        raise RuntimeError("browser crashed")

    with pytest.raises(PostingUnavailableError):
        await fetch_posting(URL, transport=transport(status=404), render=broken_render)

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    with pytest.raises(PostingUnavailableError):
        await fetch_posting(URL, transport=httpx.MockTransport(refuse))
