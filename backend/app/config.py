from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All runtime settings, read from the environment or a `.env` file (FND-4.2)."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://bane:bane@localhost:5432/bane"
    data_dir: Path = REPO_ROOT / "data"

    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.1:8b"
    llm_timeout_s: float = Field(default=120, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)
    # Context window in tokens. 8192 fits an 8B model on an 8 GB GPU with room to spare.
    llm_num_ctx: int = Field(default=8192, ge=2048)
    # Answer LLM prompts with canned replies instead of calling Ollama. For E2E tests and demos.
    llm_fake: bool = False

    max_upload_mb: int = Field(default=10, gt=0)

    # Web Job Scraper (spec 02)
    # "fake" returns canned postings, for trying the app and for E2E tests.
    job_source: Literal["google_playwright", "serpapi", "fake"] = "google_playwright"
    serpapi_key: str | None = None
    scraper_delay_s: float = Field(default=2.0, ge=0)
    scraper_headless: bool = True
    # A Chromium binary to use instead of Playwright's own download (optional).
    scraper_chromium_path: str | None = None
    google_jobs_url: str = "https://www.google.com/search"
    scorer_max_chars: int = Field(default=6000, ge=500)
    # Weights for the overall score; they're normalised, so only their ratios matter.
    score_weight_title: float = Field(default=30, ge=0)
    score_weight_skills: float = Field(default=30, ge=0)
    score_weight_experience: float = Field(default=15, ge=0)
    score_weight_level: float = Field(default=15, ge=0)
    score_weight_location: float = Field(default=10, ge=0)

    # Resume Rounder (spec 03)
    # LibreOffice measures page counts and exports PDFs. A full path if it isn't on PATH.
    soffice_path: str = "soffice"
    soffice_timeout_s: float = Field(default=120, gt=0)
    # Open job posting URLs in a browser when the plain download has too little text.
    posting_browser_fallback: bool = True

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
