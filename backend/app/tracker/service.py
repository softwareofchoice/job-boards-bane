"""Job Application Tracker logic, independent of HTTP."""

import uuid
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.files import FileStore
from app.tracker.models import Application, search_expression
from app.tracker.schemas import (
    RESUME_TYPES,
    SCREENSHOT_TYPES,
    ApplicationIn,
    ApplicationOut,
    DuplicateCheck,
    FileOut,
)


@dataclass(frozen=True)
class Upload:
    filename: str
    data: bytes


def normalize_url(url: str) -> str:
    """The form of a posting URL used to spot duplicates (TRK-1.7).

    Lower-cases the scheme and host, drops the fragment, `utm_*` tracking parameters and a
    trailing slash. The path and other query parameters keep their case: they often identify
    the posting.
    """
    parts = urlsplit(url.strip())
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")
        ]
    )
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def create_application(
    session: Session,
    store: FileStore,
    data: ApplicationIn,
    resume: Upload,
    screenshot: Upload | None,
) -> Application:
    """Save the files and the row together: on any failure neither is kept (TRK-1.2, TRK-1.5)."""
    with store.transaction() as files:
        resume_file = files.save("resume", resume.filename, resume.data, RESUME_TYPES)
        screenshot_file = (
            files.save("screenshot", screenshot.filename, screenshot.data, SCREENSHOT_TYPES)
            if screenshot
            else None
        )
        application = Application(
            job_title=data.job_title,
            company_name=data.company_name,
            posting_url=data.posting_url,
            posting_url_normalized=normalize_url(data.posting_url),
            resume=resume_file,
            screenshot=screenshot_file,
        )
        session.add(application)
        try:
            session.commit()
        except BaseException:
            session.rollback()
            raise
    session.refresh(application)
    return application


def check_duplicate(session: Session, url: str) -> DuplicateCheck:
    previous = session.scalar(
        select(func.max(Application.created_at)).where(
            Application.posting_url_normalized == normalize_url(url)
        )
    )
    return DuplicateCheck(duplicate=previous is not None, previous_created_at=previous)


def escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_applications(
    session: Session, q: str, page: int, page_size: int
) -> tuple[list[Application], int]:
    """Newest first, optionally filtered by text in the title or company (TRK-2.1 to TRK-2.3)."""
    query = select(Application)
    if q.strip():
        pattern = f"%{escape_like(q.strip())}%"
        query = query.where(search_expression().ilike(pattern, escape="\\"))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Application.created_at.desc(), Application.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return list(rows), total


def get_application(session: Session, application_id: uuid.UUID) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise NotFoundError("Application not found.")
    return application


def delete_application(session: Session, store: FileStore, application_id: uuid.UUID) -> None:
    """Remove the row and its files (TRK-3.1). Files go after the commit, so a failure to
    delete one can't leave a row pointing at a missing file."""
    application = get_application(session, application_id)
    files = [f for f in (application.resume, application.screenshot) if f is not None]
    session.delete(application)
    session.flush()
    for stored in files:
        session.delete(stored)
    session.commit()
    for stored in files:
        store.delete_quietly(stored)


def to_out(application: Application) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        job_title=application.job_title,
        company_name=application.company_name,
        posting_url=application.posting_url,
        screenshot=FileOut.from_stored(application.screenshot) if application.screenshot else None,
        resume=FileOut.from_stored(application.resume),
        created_at=application.created_at,
    )
