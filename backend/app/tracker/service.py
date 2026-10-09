"""Job Application Tracker logic, independent of HTTP."""

import uuid
from collections import Counter
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.core.files import FileStore
from app.core.uploads import Upload
from app.tracker.models import Application, StatusChange, search_expression
from app.tracker.schemas import (
    RESUME_TYPES,
    SCREENSHOT_TYPES,
    ApplicationIn,
    ApplicationOut,
    DuplicateCheck,
    FileOut,
    FlowPath,
    StatusChangeOut,
    StatusFlow,
)
from app.tracker.status import LABELS, Status, allowed_next, can_change, flow_path


class InvalidStatusChangeError(AppError):
    status_code = 409
    code = "invalid_status_change"


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
            status=Status.APPLIED,
        )
        # TRK-4.1: every application starts as "applied". Both default to now() in the same
        # transaction, so the change is dated exactly with created_at.
        application.status_history.append(StatusChange(to_status=Status.APPLIED))
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
    session: Session, q: str, page: int, page_size: int, status: Status | None = None
) -> tuple[list[Application], int]:
    """Newest first, optionally filtered by text in the title or company (TRK-2.1 to TRK-2.3)
    and by status (TRK-4.7)."""
    query = select(Application)
    if status is not None:
        query = query.where(Application.status == status)
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


def _locked(session: Session, application_id: uuid.UUID) -> Application:
    """The application, locked until commit so two changes can't both apply."""
    application = session.scalar(
        select(Application).where(Application.id == application_id).with_for_update(of=Application)
    )
    if application is None:
        raise NotFoundError("Application not found.")
    return application


def change_status(session: Session, application_id: uuid.UUID, new: Status) -> Application:
    """Move to `new` if the transitions allow it, recording the change (TRK-4.2 to TRK-4.4)."""
    application = _locked(session, application_id)
    current = Status(application.status)
    if not can_change(current, new):
        allowed = allowed_next(current)
        options = " or ".join(LABELS[s] for s in allowed)
        reason = (
            f"From {LABELS[current]} you can move to {options}."
            if allowed
            else f"{LABELS[current]} is final."
        )
        session.rollback()
        raise InvalidStatusChangeError(
            f"Can't change the status from {LABELS[current]} to {LABELS[new]}. {reason}",
            allowed=[s.value for s in allowed],
        )
    application.status_history.append(StatusChange(from_status=current, to_status=new))
    application.status = new
    session.commit()
    session.refresh(application)
    return application


def undo_status_change(session: Session, application_id: uuid.UUID) -> Application:
    """Remove the latest change and go back to the status before it (TRK-4.6)."""
    application = _locked(session, application_id)
    history = application.status_history
    latest = history[-1] if history else None
    if latest is None or latest.from_status is None:
        session.rollback()
        raise InvalidStatusChangeError("There's no status change to undo.", allowed=[])
    application.status = latest.from_status
    history.remove(latest)
    session.commit()
    session.refresh(application)
    return application


def status_flow(session: Session) -> StatusFlow:
    """How many applications took each path through the statuses (TRK-5.1)."""
    rows = session.execute(
        select(StatusChange.application_id, StatusChange.to_status).order_by(
            StatusChange.application_id, StatusChange.changed_at, StatusChange.id
        )
    ).all()
    histories: dict[uuid.UUID, list[Status]] = {}
    for application_id, to_status in rows:
        histories.setdefault(application_id, []).append(Status(to_status))
    counts = Counter(flow_path(h) for h in histories.values())
    paths = [
        FlowPath(statuses=list(path), count=count)
        for path, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return StatusFlow(total=len(histories), paths=paths)


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
        status=Status(application.status),
        allowed_next=list(allowed_next(Status(application.status))),
        status_history=[StatusChangeOut.model_validate(c) for c in application.status_history],
    )
