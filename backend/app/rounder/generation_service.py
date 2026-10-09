"""Saving generation requests, running them as background jobs, and their downloads (RND-4)."""

import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import NotFoundError
from app.core.files import DOCX, PDF, FileStore
from app.core.jobs import JobContext, create_job
from app.core.llm import LLM
from app.core.models import StoredFile
from app.core.uploads import Upload
from app.rounder import skills_service
from app.rounder.generate import GenerationInput, generate
from app.rounder.matching import SkillNote
from app.rounder.models import ResumeGeneration
from app.rounder.pages import PageMeasurer
from app.rounder.posting import Renderer, fetch_posting
from app.rounder.schemas import (
    TEMPLATE_TYPES,
    FileLink,
    GenerationDetail,
    GenerationFields,
    GenerationSummary,
)

JOB_KIND = "resume_generation"


def create_generation(
    session: Session,
    store: FileStore,
    fields: GenerationFields,
    template: Upload,
    target_pages: Decimal,
    heading_idx: int | None,
    model: str,
) -> ResumeGeneration:
    """Store the template and the request; the caller starts the job (RND-4.4)."""
    job = create_job(session, JOB_KIND)
    with store.transaction() as files:
        stored = files.save("rounder_template", template.filename, template.data, TEMPLATE_TYPES)
        generation = ResumeGeneration(
            job_id=job.id,
            template=stored,
            job_title=fields.job_title,
            company_name=fields.company_name,
            posting_url=fields.posting_url,
            # A URL's text is downloaded by the job and saved here then.
            posting_text=fields.posting_text or "",
            target_pages=target_pages,
            experience_heading_idx=heading_idx,
            model=model,
        )
        session.add(generation)
        try:
            session.commit()
        except BaseException:
            session.rollback()
            raise
    session.refresh(generation)
    return generation


async def run_generation(
    ctx: JobContext,
    generation_id: uuid.UUID,
    llm: LLM,
    measurer: PageMeasurer,
    renderer: Renderer | None,
    store: FileStore,
    sessions: sessionmaker[Session],
) -> None:
    ctx.update_progress(step="reading_posting")
    with sessions() as session:
        generation = get_generation(session, generation_id)
        template = store.path(generation.template).read_bytes()
        skills = [
            SkillNote(s.skill_name, s.role, s.summary) for s in skills_service.list_skills(session)
        ]
        posting_url, posting_text = generation.posting_url, generation.posting_text
        inp = GenerationInput(
            template=template,
            posting_text=posting_text,
            job_title=generation.job_title,
            company_name=generation.company_name,
            target_pages=float(generation.target_pages),
            heading_idx=generation.experience_heading_idx,
            skills=skills,
        )
    if posting_url:
        inp.posting_text = await fetch_posting(posting_url, render=renderer)
        with sessions() as session:
            get_generation(session, generation_id).posting_text = inp.posting_text
            session.commit()

    result = await generate(inp, llm, measurer, ctx.update_progress)

    with sessions() as session:
        generation = get_generation(session, generation_id)
        with store.transaction() as files:
            generation.output_docx = files.save(
                "rounder_output", download_name(generation, "docx"), result.docx
            )
            generation.output_pdf = files.save(
                "rounder_output", download_name(generation, "pdf"), result.pdf
            )
            generation.final_pages = result.page_count
            generation.experience_heading_idx = result.heading_idx
            generation.report = result.report.model_dump(mode="json")
            session.commit()


def get_generation(session: Session, generation_id: uuid.UUID) -> ResumeGeneration:
    generation = session.get(ResumeGeneration, generation_id)
    if generation is None:
        raise NotFoundError("Generated resume not found.")
    return generation


def list_generations(session: Session) -> list[ResumeGeneration]:
    return list(
        session.scalars(select(ResumeGeneration).order_by(ResumeGeneration.created_at.desc()))
    )


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:60]


def download_name(generation: ResumeGeneration, ext: str) -> str:
    """`<Company>-<JobTitle>-resume.docx` (RND-4.3)."""
    parts = [p for p in (_slug(generation.company_name), _slug(generation.job_title)) if p]
    return "-".join([*parts, "resume"]) + f".{ext}"


def output_file(generation: ResumeGeneration, ext: str) -> tuple[StoredFile, str]:
    stored = generation.output_docx if ext == "docx" else generation.output_pdf
    if stored is None:
        raise NotFoundError("This resume hasn't been generated yet.")
    return stored, DOCX if ext == "docx" else PDF


def to_summary(generation: ResumeGeneration) -> GenerationSummary:
    return GenerationSummary(
        id=generation.id,
        job_id=generation.job_id,
        job_title=generation.job_title,
        company_name=generation.company_name,
        posting_url=generation.posting_url,
        target_pages=generation.target_pages,
        final_pages=generation.final_pages,
        status=generation.job.status,
        created_at=generation.created_at,
    )


def to_detail(generation: ResumeGeneration) -> GenerationDetail:
    base = f"/api/rounder/generations/{generation.id}"

    def link(stored: StoredFile | None, ext: str) -> FileLink | None:
        if stored is None:
            return None
        return FileLink(url=f"{base}/resume.{ext}", filename=download_name(generation, ext))

    return GenerationDetail(
        **to_summary(generation).model_dump(),
        progress=generation.job.progress,
        error=generation.job.error,
        model=generation.model,
        report=generation.report,
        docx=link(generation.output_docx, "docx"),
        pdf=link(generation.output_pdf, "pdf"),
    )
