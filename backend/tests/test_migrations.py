from collections.abc import Iterator

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from alembic import command
from app.core.db import Base, get_engine
from tests.conftest import TEST_DATABASE_URL, alembic_config

SCRATCH_DB = "bane_migration_test"


@pytest.fixture
def scratch_url() -> Iterator[str]:
    """A separate, empty database so up/down migrations don't disturb other tests."""
    admin = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH_DB}"))
        conn.execute(text(f"CREATE DATABASE {SCRATCH_DB}"))
    url = make_url(TEST_DATABASE_URL).set(database=SCRATCH_DB)
    yield url.render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH_DB} WITH (FORCE)"))
    admin.dispose()


def test_migrations_upgrade_and_downgrade_cleanly(scratch_url: str) -> None:
    config = alembic_config(scratch_url)
    engine = create_engine(scratch_url)

    command.upgrade(config, "head")
    assert {"stored_files", "jobs"} <= set(inspect(engine).get_table_names())

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}

    command.upgrade(config, "head")
    engine.dispose()


def test_models_match_migrations() -> None:
    """Fails if a model was changed without a migration (or the other way round)."""
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
