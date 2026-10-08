import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.models import Job, StoredFile


class Skill(Base):
    """One saved skill: what it is, the role it was used in, and what was done (RND-1).

    The spec's "SKILLS" table. A skill name may repeat across roles, but not within one.
    """

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    skill_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# RND-1.3: the same skill name and role, ignoring case, can only be saved once.
Index(
    "uq_skills_name_role",
    func.lower(Skill.skill_name),
    func.lower(Skill.role),
    unique=True,
)


class ResumeGeneration(Base):
    """One tailored resume: its inputs, the job that made it, outputs and report (RND-4.4)."""

    __tablename__ = "resume_generations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    template_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_files.id")
    )
    output_docx_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_files.id")
    )
    output_pdf_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stored_files.id")
    )
    job_title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    posting_url: Mapped[str | None] = mapped_column(String(2048))
    posting_text: Mapped[str] = mapped_column(Text)
    target_pages: Mapped[Decimal] = mapped_column(Numeric(2, 1))
    experience_heading_idx: Mapped[int | None] = mapped_column(Integer)
    final_pages: Mapped[int | None] = mapped_column(Integer)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(lazy="joined")
    template: Mapped[StoredFile] = relationship(foreign_keys=[template_file_id], lazy="joined")
    output_docx: Mapped[StoredFile | None] = relationship(
        foreign_keys=[output_docx_file_id], lazy="joined"
    )
    output_pdf: Mapped[StoredFile | None] = relationship(
        foreign_keys=[output_pdf_file_id], lazy="joined"
    )
