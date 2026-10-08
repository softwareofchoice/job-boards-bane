import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.models import Job


class ScrapeRun(Base):
    """One search: its inputs, where it came from, and its postings (SCR-5.5)."""

    __tablename__ = "scrape_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"))
    options: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text)
    stopped_reason: Mapped[str | None] = mapped_column(Text)
    pulled_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    model: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(lazy="joined")
    postings: Mapped[list["ScrapedPosting"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(ScrapedPosting.rank.asc().nulls_last(), ScrapedPosting.position)",
    )


class ScrapedPosting(Base):
    __tablename__ = "scraped_postings"
    __table_args__ = (Index("ix_scraped_postings_run_rank", "run_id", "rank"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scrape_runs.id", ondelete="CASCADE")
    )
    # Order in which the source returned it; keeps unscored postings in a stable order.
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    via: Mapped[str | None] = mapped_column(Text)
    salary_text: Mapped[str | None] = mapped_column(Text)
    posted_text: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    sub_scores: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    matched_skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default="{}"
    )
    missing_skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default="{}"
    )
    rationale: Mapped[str | None] = mapped_column(Text)
    score_error: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    run: Mapped[ScrapeRun] = relationship(back_populates="postings")
