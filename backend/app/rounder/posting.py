"""Getting a job posting's text from its URL (RND-2.3, RND-2.4)."""

import logging
from collections.abc import Awaitable, Callable

import httpx
import trafilatura

from app.core.errors import AppError
from app.rounder.schemas import MAX_POSTING_CHARS, MIN_POSTING_CHARS

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
TIMEOUT_S = 15

# Renders a page in a real browser and returns its HTML (for sites built with JavaScript).
Renderer = Callable[[str], Awaitable[str]]


class PostingUnavailableError(AppError):
    status_code = 422
    code = "posting_unavailable"


def extract_text(html: str, url: str | None = None) -> str:
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
    return (text or "").strip()


async def download(url: str, transport: httpx.AsyncBaseTransport | None = None) -> str:
    async with httpx.AsyncClient(
        timeout=TIMEOUT_S,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
        transport=transport,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def playwright_renderer(chromium_path: str | None = None) -> Renderer:
    async def render(url: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, executable_path=chromium_path)
            try:
                page = await browser.new_page(user_agent=USER_AGENT)
                await page.goto(url, wait_until="networkidle", timeout=TIMEOUT_S * 1000)
                return await page.content()
            finally:
                await browser.close()

    return render


async def fetch_posting(
    url: str,
    *,
    render: Renderer | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """The posting's main text. Falls back to a real browser when the plain download has too
    little text. Raises PostingUnavailableError when neither works (RND-2.4)."""
    text = ""
    try:
        text = extract_text(await download(url, transport), url)
    except httpx.HTTPError as exc:
        logger.info("Downloading posting %s failed: %s", url, exc)
    if len(text) < MIN_POSTING_CHARS and render is not None:
        try:
            text = extract_text(await render(url), url)
        except Exception as exc:  # any browser failure just means "couldn't read it"
            logger.info("Rendering posting %s failed: %s", url, exc)
    if len(text) < MIN_POSTING_CHARS:
        raise PostingUnavailableError(
            "Couldn't read the job posting from this address. Paste the description instead."
        )
    return text[:MAX_POSTING_CHARS]
