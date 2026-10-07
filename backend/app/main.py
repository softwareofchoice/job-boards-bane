import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.db import DatabaseUnavailableError, check_connection, get_engine, get_sessionmaker
from app.core.errors import register_error_handlers
from app.core.jobs import fail_interrupted_jobs
from app.core.logging import add_request_id_middleware, configure_logging
from app.core.router import router as core_router
from app.tracker.router import router as tracker_router

logger = logging.getLogger(__name__)


def startup() -> None:
    """Checks and housekeeping before serving requests. Exits if the database is down (FND-2.4)."""
    settings = get_settings()
    try:
        check_connection(get_engine())
    except DatabaseUnavailableError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with get_sessionmaker()() as session:
        if count := fail_interrupted_jobs(session):
            logger.warning("Marked %d interrupted background job(s) as failed", count)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    startup()
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Job Board's Bane", lifespan=lifespan)
    add_request_id_middleware(app)
    register_error_handlers(app)
    app.include_router(core_router)
    app.include_router(tracker_router)
    return app


app = create_app()
