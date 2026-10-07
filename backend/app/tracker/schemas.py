import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.models import StoredFile

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
RESUME_TYPES = {PDF: "PDF", DOCX: "DOCX"}
SCREENSHOT_TYPES = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WebP"}

MAX_URL_LENGTH = 2048


def check_http_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("Enter a full web address starting with http:// or https://")
    return value


Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
HttpUrlText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_URL_LENGTH),
    AfterValidator(check_http_url),
]


class ApplicationIn(BaseModel):
    """The text fields of the log-application form (TRK-1.1). Files are checked separately."""

    job_title: Name
    company_name: Name
    posting_url: HttpUrlText


class FileOut(BaseModel):
    id: uuid.UUID
    url: str
    original_name: str
    content_type: str
    size_bytes: int

    @classmethod
    def from_stored(cls, stored: StoredFile) -> "FileOut":
        return cls(
            id=stored.id,
            url=f"/api/files/{stored.id}",
            original_name=stored.original_name,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
        )


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_title: str
    company_name: str
    posting_url: str
    screenshot: FileOut | None
    resume: FileOut
    created_at: datetime


class ApplicationPage(BaseModel):
    items: list[ApplicationOut]
    total: int
    page: int
    page_size: int


class DuplicateCheck(BaseModel):
    duplicate: bool
    previous_created_at: datetime | None = None


class PageParams(BaseModel):
    q: str = Field(default="", max_length=200)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
