import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Point the app at the test database before any app module reads its settings.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://bane:bane@localhost:5432/bane_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="bane-test-data-")

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.core.db import Base, get_engine, get_sessionmaker  # noqa: E402
from app.core.deps import get_file_store, get_llm  # noqa: E402
from app.core.files import FileStore  # noqa: E402
from app.core.llm_fake import FakeLLMClient  # noqa: E402
from app.main import create_app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config(database_url: str = TEST_DATABASE_URL) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> Iterator[None]:
    """Start every test session from a freshly migrated, empty database."""
    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    command.upgrade(alembic_config(), "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))


@pytest.fixture
def session() -> Iterator[Session]:
    with get_sessionmaker()() as s:
        yield s


@pytest.fixture
def file_store(tmp_path: Path) -> FileStore:
    return FileStore(tmp_path / "data", max_bytes=1024 * 1024)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def client(file_store: FileStore, fake_llm: FakeLLMClient) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_file_store] = lambda: file_store
    app.dependency_overrides[get_llm] = lambda: fake_llm
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
