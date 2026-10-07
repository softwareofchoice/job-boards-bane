import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core import jobs
from app.core.db import check_connection, get_engine, get_session
from app.core.deps import get_file_store, get_llm
from app.core.errors import AppError, NotFoundError
from app.core.files import FileStore
from app.core.llm import LLM
from app.core.models import StoredFile

router = APIRouter(prefix="/api")

SessionDep = Annotated[Session, Depends(get_session)]


class HealthOut(BaseModel):
    db: Literal["ok", "error"]
    llm: Literal["ok", "error"]
    model: str
    llm_message: str | None = None


@router.get("/health")
async def health(
    llm: Annotated[LLM, Depends(get_llm)], engine: Annotated[Engine, Depends(get_engine)]
) -> HealthOut:
    """Whether the database and the local LLM can be used (FND-3.5)."""
    try:
        check_connection(engine)
        db = "ok"
    except Exception:
        db = "error"
    llm_message = None
    try:
        await llm.check()
        llm_status = "ok"
    except AppError as exc:
        llm_status, llm_message = "error", exc.message
    return HealthOut(db=db, llm=llm_status, model=llm.model, llm_message=llm_message)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str
    progress: dict[str, Any]
    error: str | None
    created_at: datetime
    finished_at: datetime | None


@router.get("/jobs/{job_id}")
def get_job(job_id: uuid.UUID, session: SessionDep) -> JobOut:
    return JobOut.model_validate(jobs.get_job(session, job_id))


@router.get("/files/{file_id}")
def download_file(
    file_id: uuid.UUID,
    session: SessionDep,
    store: Annotated[FileStore, Depends(get_file_store)],
) -> FileResponse:
    stored = session.get(StoredFile, file_id)
    if stored is None:
        raise NotFoundError("File not found.")
    # Only images are shown in the browser; everything else downloads. `nosniff` stops the
    # browser from second-guessing the stored (magic-byte checked) content type.
    inline = stored.content_type.startswith("image/")
    return FileResponse(
        store.path(stored),
        media_type=stored.content_type,
        filename=stored.original_name,
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )
