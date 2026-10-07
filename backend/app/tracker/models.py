import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, DateTime, ForeignKey, Index, String, func, literal, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.models import StoredFile


class Application(Base):
    """One job application the user logged (TRK-1). The spec's "Applications" table."""

    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_created_at", text("created_at DESC")),
        Index("ix_applications_posting_url_normalized", "posting_url_normalized"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    posting_url: Mapped[str] = mapped_column(String(2048))
    posting_url_normalized: Mapped[str] = mapped_column(String(2048))
    screenshot_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_files.id")
    )
    resume_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_files.id")
    )
    # Always set by the database (TRK-1.3); the API never accepts it.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    screenshot: Mapped[StoredFile | None] = relationship(
        foreign_keys=[screenshot_file_id], lazy="joined"
    )
    resume: Mapped[StoredFile] = relationship(foreign_keys=[resume_file_id], lazy="joined")


def search_expression() -> ColumnElement[str]:
    """Title and company as one string, for search (TRK-2.2). Indexed below; queries must use it."""
    return Application.job_title.op("||")(literal(" ", literal_execute=True)).op("||")(
        Application.company_name
    )


# Trigram index so `search_expression() ILIKE '%...%'` is fast.
Index(
    "ix_applications_search",
    search_expression().label("search"),
    postgresql_using="gin",
    postgresql_ops={"search": "gin_trgm_ops"},
)
