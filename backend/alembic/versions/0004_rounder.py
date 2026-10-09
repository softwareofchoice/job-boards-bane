"""skills and resume_generations

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("skill_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_skills_name_role",
        "skills",
        [sa.text("lower((skill_name)::text)"), sa.text("lower((role)::text)")],
        unique=True,
    )
    op.create_table(
        "resume_generations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False
        ),
        sa.Column(
            "template_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_files.id"),
            nullable=False,
        ),
        sa.Column(
            "output_docx_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_files.id"),
            nullable=True,
        ),
        sa.Column(
            "output_pdf_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stored_files.id"),
            nullable=True,
        ),
        sa.Column("job_title", sa.String(200), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("posting_url", sa.String(2048), nullable=True),
        sa.Column("posting_text", sa.Text(), nullable=False),
        sa.Column("target_pages", sa.Numeric(2, 1), nullable=False),
        sa.Column("experience_heading_idx", sa.Integer(), nullable=True),
        sa.Column("final_pages", sa.Integer(), nullable=True),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("resume_generations")
    op.drop_index("uq_skills_name_role", table_name="skills")
    op.drop_table("skills")
