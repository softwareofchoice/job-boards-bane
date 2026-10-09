"""application status and its history (TRK-4)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("status", sa.String(20), nullable=False, server_default="applied"),
    )
    op.create_check_constraint(
        "applications_status_check",
        "applications",
        "status IN ('applied', 'interviewing', 'offer', 'rejected')",
    )
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_table(
        "application_status_changes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_status_changes_application",
        "application_status_changes",
        ["application_id", "changed_at"],
    )
    # Every existing application starts with "applied", dated when it was logged (TRK-4.1).
    op.execute(
        "INSERT INTO application_status_changes (application_id, from_status, to_status, "
        "changed_at) SELECT id, NULL, 'applied', created_at FROM applications"
    )


def downgrade() -> None:
    op.drop_index("ix_status_changes_application", table_name="application_status_changes")
    op.drop_table("application_status_changes")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_constraint("applications_status_check", "applications", type_="check")
    op.drop_column("applications", "status")
