from app.config import get_settings
from app.scraper.sources.base import JobSource
from app.scraper.sources.fake import FakeJobSource
from app.scraper.sources.google_playwright import GooglePlaywrightSource
from app.scraper.sources.serpapi import SerpApiSource


def get_job_source() -> JobSource:
    """The source chosen by JOB_SOURCE. Tests override this dependency."""
    settings = get_settings()
    if settings.job_source == "serpapi":
        return SerpApiSource(settings.serpapi_key)
    if settings.job_source == "fake":
        return FakeJobSource()
    return GooglePlaywrightSource(
        base_url=settings.google_jobs_url,
        delay_s=settings.scraper_delay_s,
        headless=settings.scraper_headless,
        chromium_path=settings.scraper_chromium_path,
    )
