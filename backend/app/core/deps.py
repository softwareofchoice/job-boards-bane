"""FastAPI dependencies for the shared services. Tests override these."""

from functools import lru_cache

from app.config import get_settings
from app.core.files import FileStore
from app.core.llm import LLM, LLMClient


@lru_cache
def get_file_store() -> FileStore:
    settings = get_settings()
    return FileStore(settings.data_dir, settings.max_upload_bytes)


@lru_cache
def get_llm() -> LLM:
    settings = get_settings()
    return LLMClient(
        settings.llm_base_url,
        settings.llm_model,
        timeout_s=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
    )
