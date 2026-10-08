"""Collects postings from Google's jobs view with a real browser (SCR-3.1, SCR-3.4 to SCR-3.6).

Note: automated use of Google search is against Google's terms of service and may be blocked
(see open question Q-4). The SerpAPI source is the licensed alternative.
"""

import asyncio
import logging
import random
from datetime import UTC, datetime
from urllib.parse import urlencode

from playwright.async_api import Browser, Page, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from app.scraper.schemas import RawPosting, SearchOptions, SourceResult, StopReason
from app.scraper.sources import google_selectors as sel
from app.scraper.sources.base import JobSourceError, ProgressFn, build_query, date_chip
from app.scraper.sources.google_parse import (
    LayoutChangedError,
    is_blocked,
    merge,
    parse_card,
    parse_detail,
)

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


class GooglePlaywrightSource:
    name = "google_playwright"

    def __init__(
        self,
        *,
        base_url: str = "https://www.google.com/search",
        delay_s: float = 2.0,
        headless: bool = True,
        chromium_path: str | None = None,
        wait_timeout_ms: int = 15_000,
    ) -> None:
        self.base_url = base_url
        self.delay_s = delay_s
        self.headless = headless
        self.chromium_path = chromium_path
        self.wait_timeout_ms = wait_timeout_ms

    def search_url(self, opts: SearchOptions) -> str:
        chip = f"date_posted:{date_chip(opts.days_since_posting)}"
        query = {"q": build_query(opts), "ibp": "htl;jobs", "hl": "en", "htichips": chip}
        return f"{self.base_url}?{urlencode(query)}"

    async def search(
        self, opts: SearchOptions, limit: int, on_progress: ProgressFn
    ) -> SourceResult:
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(
                    headless=self.headless, executable_path=self.chromium_path or None
                )
            except PlaywrightError as exc:
                raise JobSourceError(
                    "Couldn't start the browser for scraping. Run `make scraper-browser` "
                    "(or set SCRAPER_CHROMIUM_PATH)."
                ) from exc
            try:
                return await self._collect(browser, opts, limit, on_progress)
            finally:
                await browser.close()

    async def _collect(
        self, browser: Browser, opts: SearchOptions, limit: int, on_progress: ProgressFn
    ) -> SourceResult:
        context = await browser.new_context(locale="en-US", user_agent=USER_AGENT)
        page = await context.new_page()
        page.set_default_timeout(self.wait_timeout_ms)
        try:
            await page.goto(self.search_url(opts))
        except PlaywrightError as exc:
            raise JobSourceError(
                f"Couldn't load Google's job search: {str(exc).splitlines()[0]}"
            ) from exc
        await self._dismiss_consent(page)

        postings: list[RawPosting] = []
        seen = 0
        now = datetime.now(UTC)
        stop: StopReason | None = None
        list_selector = sel.any_of(sel.LIST_ITEM)

        if await self._blocked(page):
            return SourceResult(postings=[], stopped_reason="blocked")
        try:
            await page.wait_for_selector(list_selector)
        except PlaywrightTimeout:
            stop = "blocked" if await self._blocked(page) else "layout_changed"
            return SourceResult(postings=[], stopped_reason=stop)

        while len(postings) < limit:
            items = page.locator(list_selector)
            count = await items.count()
            if seen >= count:
                stop = "exhausted"
                break
            for index in range(seen, count):
                if len(postings) >= limit:
                    break
                item = items.nth(index)
                card = parse_card(await item.evaluate("el => el.outerHTML"))
                seen = index + 1
                if card is None:
                    continue
                try:
                    await item.scroll_into_view_if_needed()
                    await item.click()
                    await self._pause()
                    await self._expand_description(page)
                    detail = parse_detail(await page.content())
                except LayoutChangedError:
                    stop = "layout_changed"
                    break
                except PlaywrightTimeout:
                    stop = "blocked" if await self._blocked(page) else "layout_changed"
                    break
                if await self._blocked(page):
                    stop = "blocked"
                    break
                postings.append(merge(card, detail, now, page.url))
                on_progress(len(postings))
            if stop is not None:
                break
            # Scrolling to the end of the list makes Google load the next batch.
            last = items.nth(count - 1)
            await last.scroll_into_view_if_needed()
            await last.hover()
            await page.mouse.wheel(0, 3000)
            await self._pause()
            if await page.locator(list_selector).count() == count:
                if len(postings) < limit:
                    stop = "exhausted"
                break

        logger.info("Google source collected %d postings (stop: %s)", len(postings), stop)
        return SourceResult(postings=postings, stopped_reason=stop)

    async def _pause(self) -> None:
        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s + random.uniform(0, self.delay_s / 2))

    async def _blocked(self, page: Page) -> bool:
        try:
            return is_blocked(await page.content(), page.url)
        except PlaywrightError:
            return False

    async def _dismiss_consent(self, page: Page) -> None:
        for selector in sel.CONSENT_BUTTONS:
            button = page.locator(selector).first
            try:
                if await button.is_visible(timeout=1000):
                    await button.click()
                    await page.wait_for_load_state()
                    return
            except PlaywrightError:
                continue

    async def _expand_description(self, page: Page) -> None:
        more = page.locator(
            f"{sel.any_of(sel.DETAIL_PANE)} >> {sel.any_of(sel.DETAIL_SHOW_MORE)}"
        ).first
        try:
            if await more.is_visible(timeout=500):
                await more.click()
        except PlaywrightError:
            pass
