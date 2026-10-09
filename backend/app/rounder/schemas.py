import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.files import DOCX
from app.core.validation import HttpUrlText

TEMPLATE_TYPES = {DOCX: "Word (.docx)"}
TARGET_PAGES = (Decimal("1"), Decimal("1.5"), Decimal("2"), Decimal("3"))
MIN_POSTING_CHARS = 200
MAX_POSTING_CHARS = 20_000


SkillName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Summary = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


def check_posting_text(value: str) -> str:
    if len(value) < MIN_POSTING_CHARS:
        raise ValueError(
            f"Paste the whole job description (at least {MIN_POSTING_CHARS} characters)."
        )
    if len(value) > MAX_POSTING_CHARS:
        raise ValueError(f"The description is too long (at most {MAX_POSTING_CHARS:,} characters).")
    return value


PostingText = Annotated[
    str, StringConstraints(strip_whitespace=True), AfterValidator(check_posting_text)
]


class SkillIn(BaseModel):
    """The skill form (RND-1.1)."""

    skill_name: SkillName
    role: Name
    summary: Summary


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    skill_name: str
    role: str
    summary: str
    created_at: datetime
    updated_at: datetime


class GenerationFields(BaseModel):
    """The text fields of the generate form (RND-2.1). The template is checked separately."""

    job_title: Name
    company_name: Name
    posting_url: HttpUrlText | None = None
    posting_text: PostingText | None = None


class EntryPreview(BaseModel):
    header: str
    bullets: int


class Heading(BaseModel):
    index: int
    text: str


class Preflight(BaseModel):
    """What the system found before any LLM work (RND-2.4 to RND-2.6)."""

    template_pages: float
    suggested_target: Decimal
    experience_found: bool
    experience_heading_idx: int | None
    experience_entries: list[EntryPreview]
    headings: list[Heading]
    posting_chars: int
    skills_count: int
    warnings: list[str]


class GenerationStarted(BaseModel):
    generation_id: uuid.UUID
    job_id: uuid.UUID


class FileLink(BaseModel):
    url: str
    filename: str


class GenerationSummary(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company_name: str
    posting_url: str | None
    target_pages: Decimal
    final_pages: int | None
    status: str
    created_at: datetime


class GenerationDetail(GenerationSummary):
    progress: dict[str, Any]
    error: str | None
    model: str
    report: dict[str, Any] | None
    docx: FileLink | None
    pdf: FileLink | None


# --- LLM replies --------------------------------------------------------------------------


class PostingSkills(BaseModel):
    """RND-3.1: the skills a posting asks for, in its own words."""

    required: list[str] = Field(default_factory=list)
    preferred: list[str] = Field(default_factory=list)


class SkillPair(BaseModel):
    posting_skill: str
    saved_skill: str


class SkillPairs(BaseModel):
    pairs: list[SkillPair] = Field(default_factory=list)


class RewrittenEntry(BaseModel):
    bullets: list[str]
    skills_used: list[str] = Field(default_factory=list)


# --- Report (RND-4.2) ----------------------------------------------------------------------


class PostingSkillReport(BaseModel):
    skill: str
    kind: Literal["required", "preferred"]
    covered_by: str | None


class EntryReport(BaseModel):
    header: str
    role: str | None
    before: list[str]
    after: list[str]
    skills_used: list[str]
    kept_original_reason: str | None = None


class PagesReport(BaseModel):
    target: float
    template: float
    final: float
    attempts: int
    overflow: float | None


class Report(BaseModel):
    posting_skills: list[PostingSkillReport]
    unmatched_roles: list[str]
    entries: list[EntryReport]
    pages: PagesReport
    warnings: list[str]
