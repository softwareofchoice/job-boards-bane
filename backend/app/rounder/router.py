import asyncio
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_session, get_sessionmaker
from app.core.deps import get_file_store, get_llm
from app.core.errors import AppError
from app.core.files import FileStore
from app.core.jobs import JobContext, run_job
from app.core.llm import LLM
from app.core.uploads import Upload, read_checked_file
from app.core.validation import FieldErrors
from app.rounder import generation_service, skills_service
from app.rounder.deps import get_page_measurer, get_posting_renderer
from app.rounder.pages import PageMeasurer
from app.rounder.posting import PostingUnavailableError, Renderer, fetch_posting
from app.rounder.resume_doc import (
    ExperienceSectionNotFoundError,
    InvalidTemplateError,
    ResumeModel,
    read_resume,
)
from app.rounder.schemas import (
    TARGET_PAGES,
    TEMPLATE_TYPES,
    EntryPreview,
    GenerationDetail,
    GenerationFields,
    GenerationStarted,
    GenerationSummary,
    Heading,
    Preflight,
    SkillIn,
    SkillOut,
)

router = APIRouter(prefix="/api/rounder", tags=["rounder"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[FileStore, Depends(get_file_store)]
LLMDep = Annotated[LLM, Depends(get_llm)]
MeasurerDep = Annotated[PageMeasurer, Depends(get_page_measurer)]
RendererDep = Annotated[Renderer | None, Depends(get_posting_renderer)]

POSTING_CHOICE = "Provide a job posting URL or paste the description"


class NoSkillsError(AppError):
    status_code = 409
    code = "no_skills"


# --- Skills (RND-1) -------------------------------------------------------------------------


@router.post("/skills", status_code=status.HTTP_201_CREATED)
def create_skill(data: SkillIn, session: SessionDep) -> SkillOut:
    return SkillOut.model_validate(skills_service.create_skill(session, data))


@router.get("/skills")
def list_skills(
    session: SessionDep, role: Annotated[str | None, Query(max_length=200)] = None
) -> list[SkillOut]:
    return [SkillOut.model_validate(s) for s in skills_service.list_skills(session, role)]


@router.get("/skills/roles")
def list_roles(session: SessionDep) -> list[str]:
    return skills_service.list_roles(session)


@router.get("/skills/{skill_id}")
def get_skill(skill_id: uuid.UUID, session: SessionDep) -> SkillOut:
    return SkillOut.model_validate(skills_service.get_skill(session, skill_id))


@router.put("/skills/{skill_id}")
def update_skill(skill_id: uuid.UUID, data: SkillIn, session: SessionDep) -> SkillOut:
    return SkillOut.model_validate(skills_service.update_skill(session, skill_id, data))


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: uuid.UUID, session: SessionDep) -> None:
    skills_service.delete_skill(session, skill_id)


# --- Generations (RND-2 to RND-4) -----------------------------------------------------------


@dataclass
class _Form:
    fields: GenerationFields
    template: Upload
    model: ResumeModel | None
    headings: list[Heading]


def _parse_heading_idx(errors: FieldErrors, raw: str) -> int | None:
    if not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError:
        errors.add("experience_heading_idx", "Choose a heading from the list.")
        return None


async def _read_form(
    errors: FieldErrors,
    store: FileStore,
    template: UploadFile | None,
    job_title: str,
    company_name: str,
    posting_url: str,
    posting_text: str,
    heading_idx: int | None,
) -> _Form | None:
    """Check the generate form's fields and read the template (RND-2.1, RND-2.2, RND-2.5).

    An unfound experience section is not an error here: the result says so and lists the
    headings, so the user can choose one.
    """
    if bool(posting_url.strip()) == bool(posting_text.strip()):
        errors.add("posting", POSTING_CHOICE)
    fields = errors.validate(
        GenerationFields,
        {
            "job_title": job_title,
            "company_name": company_name,
            "posting_url": posting_url.strip() or None,
            "posting_text": posting_text.strip() or None,
        },
    )
    upload = await read_checked_file(
        errors, "template", template, TEMPLATE_TYPES, store, required=True
    )
    model, headings = None, []
    if upload is not None:
        try:
            model = read_resume(upload.data, heading_idx)
            headings = [Heading(index=h.index, text=h.text) for h in model.headings]
        except InvalidTemplateError as exc:
            errors.add("template", exc.message)
        except ExperienceSectionNotFoundError as exc:
            headings = [Heading(index=h.index, text=h.text) for h in exc.headings]
            if heading_idx is not None:
                errors.add("experience_heading_idx", "That isn't a heading in this resume.")
    if fields is None or upload is None:
        return None
    return _Form(fields, upload, model, headings)


def suggested_target(pages: float) -> Decimal:
    """The smallest allowed target that fits the template as it is (RND-2.1)."""
    return next((t for t in TARGET_PAGES if float(t) >= pages - 0.02), TARGET_PAGES[-1])


@router.post("/generations/preflight")
async def preflight(
    session: SessionDep,
    store: StoreDep,
    measurer: MeasurerDep,
    renderer: RendererDep,
    template: Annotated[UploadFile | None, File()] = None,
    job_title: Annotated[str, Form()] = "",
    company_name: Annotated[str, Form()] = "",
    posting_url: Annotated[str, Form()] = "",
    posting_text: Annotated[str, Form()] = "",
    experience_heading_idx: Annotated[str, Form()] = "",
) -> Preflight:
    """Everything that can go wrong before any LLM work, checked while the user waits."""
    errors = FieldErrors()
    heading_idx = _parse_heading_idx(errors, experience_heading_idx)
    form = await _read_form(
        errors, store, template, job_title, company_name, posting_url, posting_text, heading_idx
    )
    errors.raise_if_any()
    assert form is not None

    text = form.fields.posting_text or ""
    if form.fields.posting_url:
        try:
            text = await fetch_posting(form.fields.posting_url, render=renderer)
        except PostingUnavailableError as exc:  # RND-2.4
            errors.add("posting_url", exc.message)
            errors.raise_if_any()

    rendered = await asyncio.to_thread(measurer.render, form.template.data)
    model = form.model
    return Preflight(
        template_pages=rendered.pages,
        suggested_target=suggested_target(rendered.pages),
        experience_found=model is not None,
        experience_heading_idx=model.heading_idx if model else None,
        experience_entries=[
            EntryPreview(header=e.header_text, bullets=len(e.bullets)) for e in model.entries
        ]
        if model
        else [],
        headings=form.headings,
        posting_chars=len(text),
        skills_count=skills_service.count_skills(session),
        warnings=model.warnings if model else [],
    )


@router.post("/generations", status_code=status.HTTP_202_ACCEPTED)
async def start_generation(
    session: SessionDep,
    store: StoreDep,
    llm: LLMDep,
    measurer: MeasurerDep,
    renderer: RendererDep,
    background: BackgroundTasks,
    template: Annotated[UploadFile | None, File()] = None,
    job_title: Annotated[str, Form()] = "",
    company_name: Annotated[str, Form()] = "",
    posting_url: Annotated[str, Form()] = "",
    posting_text: Annotated[str, Form()] = "",
    target_pages: Annotated[str, Form()] = "",
    experience_heading_idx: Annotated[str, Form()] = "",
) -> GenerationStarted:
    """Start generating a tailored resume (RND-3). Progress is on the job (RND-4.1)."""
    errors = FieldErrors()
    heading_idx = _parse_heading_idx(errors, experience_heading_idx)
    target = _parse_target(errors, target_pages)
    form = await _read_form(
        errors, store, template, job_title, company_name, posting_url, posting_text, heading_idx
    )
    if form is not None and form.model is None and heading_idx is None:
        errors.add("experience_heading_idx", "Choose which heading starts your experience section.")
    errors.raise_if_any()
    assert form is not None and form.model is not None and target is not None
    if skills_service.count_skills(session) == 0:  # RND-2.6
        raise NoSkillsError("Add at least one skill before generating a resume.")

    generation = generation_service.create_generation(
        session, store, form.fields, form.template, target, heading_idx, llm.model
    )
    generation_id, sessions = generation.id, get_sessionmaker()

    async def work(ctx: JobContext) -> None:
        await generation_service.run_generation(
            ctx, generation_id, llm, measurer, renderer, store, sessions
        )

    background.add_task(run_job, generation.job_id, work, sessions)
    return GenerationStarted(generation_id=generation.id, job_id=generation.job_id)


def _parse_target(errors: FieldErrors, raw: str) -> Decimal | None:
    try:
        value = Decimal(raw.strip())
    except InvalidOperation:
        value = None
    if value not in TARGET_PAGES:
        errors.add("target_pages", "Choose 1, 1.5, 2 or 3 pages.")
        return None
    return value


@router.get("/generations")
def list_generations(session: SessionDep) -> list[GenerationSummary]:
    """Past generations, newest first (RND-4.4)."""
    return [generation_service.to_summary(g) for g in generation_service.list_generations(session)]


@router.get("/generations/{generation_id}")
def get_generation(generation_id: uuid.UUID, session: SessionDep) -> GenerationDetail:
    """Progress while running (RND-4.1), then the report and downloads (RND-4.2, RND-4.3)."""
    return generation_service.to_detail(generation_service.get_generation(session, generation_id))


def _download(
    session: Session, store: FileStore, generation_id: uuid.UUID, ext: str
) -> FileResponse:
    generation = generation_service.get_generation(session, generation_id)
    stored, media_type = generation_service.output_file(generation, ext)
    return FileResponse(
        store.path(stored),
        media_type=media_type,
        filename=generation_service.download_name(generation, ext),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/generations/{generation_id}/resume.docx")
def download_docx(generation_id: uuid.UUID, session: SessionDep, store: StoreDep) -> FileResponse:
    return _download(session, store, generation_id, "docx")


@router.get("/generations/{generation_id}/resume.pdf")
def download_pdf(generation_id: uuid.UUID, session: SessionDep, store: StoreDep) -> FileResponse:
    return _download(session, store, generation_id, "pdf")
