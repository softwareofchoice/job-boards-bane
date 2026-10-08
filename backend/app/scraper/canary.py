"""Live check that the Google source still understands Google's page (`make scraper-canary`).

Runs one small search against the real site and prints what it found. With --save, also saves
the results page to data/canary/ so selectors and fixtures can be updated from it.
"""

import argparse
import asyncio
from datetime import UTC, datetime

from playwright.async_api import async_playwright

from app.config import get_settings
from app.scraper.schemas import JobLevel, SearchOptions
from app.scraper.sources.base import JobSourceError
from app.scraper.sources.google_playwright import USER_AGENT, GooglePlaywrightSource


async def save_page(source: GooglePlaywrightSource, opts: SearchOptions) -> None:
    out_dir = get_settings().data_dir / "canary"
    out_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=source.chromium_path or None)
        page = await browser.new_page(locale="en-US", user_agent=USER_AGENT)
        await page.goto(source.search_url(opts))
        await page.wait_for_timeout(3000)
        path = out_dir / f"google-jobs-{datetime.now(UTC):%Y%m%d-%H%M%S}.html"
        path.write_text(await page.content())
        await browser.close()
    print(f"Saved the results page to {path}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default="Software Engineer")
    parser.add_argument("--location", default="Remote")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    source = GooglePlaywrightSource(
        base_url=settings.google_jobs_url,
        delay_s=settings.scraper_delay_s,
        headless=settings.scraper_headless,
        chromium_path=settings.scraper_chromium_path,
    )
    opts = SearchOptions(
        job_title=args.title,
        location=args.location,
        days_since_posting=7,
        skills=["Python"],
        years_experience=3,
        job_level=JobLevel.MID,
        jobs_pulled=args.count,
        jobs_selected=1,
    )
    if args.save:
        await save_page(source, opts)
    try:
        result = await source.search(opts, args.count, lambda n: print(f"  collected {n}"))
    except JobSourceError as exc:
        print(f"PROBLEM: {exc.message}")
        return 1
    for p in result.postings:
        print(
            f"- {p.title} | {p.company} | {p.location} | {p.posted_text} | "
            f"{len(p.description)} chars | {p.url[:60]}"
        )
    print(f"Stopped: {result.stopped_reason or 'reached the limit'}")
    ok = len(result.postings) > 0 and all(p.description for p in result.postings)
    print("OK" if ok else "PROBLEM: no postings or empty descriptions; check google_selectors.py")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
