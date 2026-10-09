"""Dependencies for the Resume Rounder. Tests override these."""

from functools import lru_cache

from app.config import get_settings
from app.rounder.pages import LibreOfficeMeasurer, PageMeasurer
from app.rounder.posting import Renderer, playwright_renderer


@lru_cache
def get_page_measurer() -> PageMeasurer:
    settings = get_settings()
    return LibreOfficeMeasurer(settings.soffice_path, settings.soffice_timeout_s)


def get_posting_renderer() -> Renderer | None:
    settings = get_settings()
    if not settings.posting_browser_fallback:
        return None
    return playwright_renderer(settings.scraper_chromium_path)
