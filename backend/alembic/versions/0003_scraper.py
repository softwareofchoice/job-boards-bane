"""scrape_runs and scraped_postings

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scrape_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False
        ),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("stopped_reason", sa.Text(), nullable=True),
        sa.Column("pulled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "scraped_postings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scrape_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("via", sa.Text(), nullable=True),
        sa.Column("salary_text", sa.Text(), nullable=True),
        sa.Column("posted_text", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("sub_scores", postgresql.JSONB(), nullable=True),
        sa.Column(
            "matched_skills", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column(
            "missing_skills", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("score_error", sa.Text(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_scraped_postings_run_rank", "scraped_postings", ["run_id", "rank"])


def downgrade() -> None:
    op.drop_index("ix_scraped_postings_run_rank", table_name="scraped_postings")
    op.drop_table("scraped_postings")
    op.drop_table("scrape_runs")
