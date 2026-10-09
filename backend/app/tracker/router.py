import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import get_file_store
from app.core.files import FileStore
from app.core.uploads import read_checked_file
from app.core.validation import MAX_URL_LENGTH, FieldErrors
from app.tracker import service
from app.tracker.schemas import (
    RESUME_TYPES,
    SCREENSHOT_TYPES,
    ApplicationIn,
    ApplicationOut,
    ApplicationPage,
    DuplicateCheck,
    PageParams,
    StatusChangeIn,
    StatusFlow,
)

router = APIRouter(prefix="/api/tracker", tags=["tracker"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[FileStore, Depends(get_file_store)]


@router.post("/applications", status_code=status.HTTP_201_CREATED)
async def create_application(
    session: SessionDep,
    store: StoreDep,
    job_title: Annotated[str, Form()] = "",
    company_name: Annotated[str, Form()] = "",
    posting_url: Annotated[str, Form()] = "",
    resume: Annotated[UploadFile | None, File()] = None,
    screenshot: Annotated[UploadFile | None, File()] = None,
) -> ApplicationOut:
    """Log an application (TRK-1). Every invalid field is reported at once (TRK-1.4)."""
    errors = FieldErrors()
    data = errors.validate(
        ApplicationIn,
        {"job_title": job_title, "company_name": company_name, "posting_url": posting_url},
    )
    resume_upload = await read_checked_file(
        errors, "resume", resume, RESUME_TYPES, store, required=True
    )
    screenshot_upload = await read_checked_file(
        errors, "screenshot", screenshot, SCREENSHOT_TYPES, store, required=False
    )
    errors.raise_if_any()
    assert data is not None and resume_upload is not None

    application = service.create_application(session, store, data, resume_upload, screenshot_upload)
    return service.to_out(application)


@router.get("/applications/check-url")
def check_url(
    session: SessionDep, url: Annotated[str, Query(max_length=MAX_URL_LENGTH)]
) -> DuplicateCheck:
    """Whether this posting was logged before (TRK-1.7). A warning only; saving is still allowed."""
    return service.check_duplicate(session, url)


@router.get("/applications")
def list_applications(
    session: SessionDep, params: Annotated[PageParams, Query()]
) -> ApplicationPage:
    rows, total = service.list_applications(
        session, params.q, params.page, params.page_size, params.status
    )
    return ApplicationPage(
        items=[service.to_out(a) for a in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/applications/{application_id}")
def get_application(application_id: uuid.UUID, session: SessionDep) -> ApplicationOut:
    return service.to_out(service.get_application(session, application_id))


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: uuid.UUID, session: SessionDep, store: StoreDep) -> None:
    service.delete_application(session, store, application_id)


@router.post("/applications/{application_id}/status")
def change_status(
    application_id: uuid.UUID, change: StatusChangeIn, session: SessionDep
) -> ApplicationOut:
    """Move the application to a new status (TRK-4.2 to TRK-4.4). 409 if not allowed."""
    return service.to_out(service.change_status(session, application_id, change.status))


@router.delete("/applications/{application_id}/status/latest")
def undo_status_change(application_id: uuid.UUID, session: SessionDep) -> ApplicationOut:
    """Undo the most recent status change (TRK-4.6)."""
    return service.to_out(service.undo_status_change(session, application_id))


@router.get("/status-flow")
def status_flow(session: SessionDep) -> StatusFlow:
    """Counts of each path through the statuses, for the parallel sets plot (TRK-5)."""
    return service.status_flow(session)
