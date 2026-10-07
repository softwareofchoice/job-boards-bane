"""applications

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "applications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("job_title", sa.String(200), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("posting_url", sa.String(2048), nullable=False),
        sa.Column("posting_url_normalized", sa.String(2048), nullable=False),
        sa.Column(
            "screenshot_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_files.id"),
            nullable=True,
        ),
        sa.Column(
            "resume_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_files.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_applications_created_at", "applications", [sa.text("created_at DESC")])
    op.create_index(
        "ix_applications_posting_url_normalized", "applications", ["posting_url_normalized"]
    )
    # Typo-tolerant search on title + company (TRK-2.2). The query must use the same expression.
    op.execute(
        "CREATE INDEX ix_applications_search ON applications "
        "USING gin ((job_title || ' ' || company_name) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_applications_search", table_name="applications")
    op.drop_index("ix_applications_posting_url_normalized", table_name="applications")
    op.drop_index("ix_applications_created_at", table_name="applications")
    op.drop_table("applications")
    # pg_trgm is left installed: other tables may come to rely on it.
