from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with get_sessionmaker()() as session:
        yield session


def safe_url(url: str) -> str:
    """The connection URL with the password hidden, for error messages."""
    return make_url(url).render_as_string(hide_password=True)


class DatabaseUnavailableError(RuntimeError):
    pass


def check_connection(engine: Engine) -> None:
    """Raise DatabaseUnavailableError naming the URL (password hidden) if unreachable (FND-2.4)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise DatabaseUnavailableError(
            f"Could not connect to the database at {safe_url(str(engine.url))}: "
            f"{type(exc).__name__}. Is Postgres running? Try `make db-up`."
        ) from exc
