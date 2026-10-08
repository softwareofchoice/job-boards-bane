import enum
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Skill = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class JobLevel(enum.StrEnum):
    INTERNSHIP = "internship"
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    STAFF_PRINCIPAL = "staff_principal"
    MANAGER = "manager"
    DIRECTOR_PLUS = "director_plus"

    @property
    def label(self) -> str:
        return {
            "internship": "Internship",
            "entry": "Entry level",
            "mid": "Mid level",
            "senior": "Senior",
            "staff_principal": "Staff / Principal",
            "manager": "Manager",
            "director_plus": "Director or above",
        }[self.value]


class SearchOptions(BaseModel):
    """What the user is looking for (SCR-1.1). Used for the form, YAML files and stored runs."""

    job_title: Text200
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    days_since_posting: int = Field(ge=1, le=60)
    skills: list[Skill] = Field(min_length=1, max_length=30)
    years_experience: int = Field(ge=0, le=50)
    job_level: JobLevel
    jobs_pulled: int = Field(ge=1, le=100)
    jobs_selected: int = Field(ge=1)

    @model_validator(mode="after")
    def selected_within_pulled(self) -> Self:
        if self.jobs_selected > self.jobs_pulled:
            raise ValueError("Jobs selected can't be more than jobs pulled")  # SCR-1.2
        if self.location == "":
            self.location = None
        return self


class RawPosting(BaseModel):
    """One posting as collected from a source, before scoring (SCR-3.2)."""

    title: str
    company: str
    location: str | None = None
    posted_at: date | None = None
    posted_text: str | None = None
    url: str
    via: str | None = None
    salary_text: str | None = None
    description: str = ""


StopReason = Literal["blocked", "layout_changed", "exhausted"]


class SourceResult(BaseModel):
    postings: list[RawPosting]
    stopped_reason: StopReason | None = None


class ScoreResponse(BaseModel):
    """What the LLM returns for one posting (SCR-4.2). The overall score is computed in code."""

    title_fit: int = Field(ge=0, le=10)
    skills: int = Field(ge=0, le=10)
    experience: int = Field(ge=0, le=10)
    level: int = Field(ge=0, le=10)
    location: int = Field(ge=0, le=10)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    rationale: str = Field(max_length=400)


class SubScores(BaseModel):
    title_fit: int
    skills: int
    experience: int
    level: int
    location: int


class PostingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    company: str
    location: str | None
    url: str
    via: str | None
    salary_text: str | None
    posted_text: str | None
    posted_at: date | None
    description: str
    score: int | None
    sub_scores: SubScores | None
    matched_skills: list[str]
    missing_skills: list[str]
    rationale: str | None
    score_error: str | None
    rank: int | None
    selected: bool


class RunSummary(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    options: SearchOptions
    source: str
    status: str
    stopped_reason: str | None
    pulled_count: int
    selected_count: int
    created_at: datetime


class RunDetail(RunSummary):
    progress: dict[str, Any]
    error: str | None
    model: str
    postings: list[PostingOut]


class RunStarted(BaseModel):
    run_id: uuid.UUID
    job_id: uuid.UUID
