import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.db import get_session, get_sessionmaker
from app.core.files import FileStore
from app.core.models import StoredFile
from app.tracker.models import Application
from app.tracker.service import escape_like
from tests.samples import EXE, JPEG, PDF, PNG, docx

URL = "/api/tracker/applications"

Files = dict[str, tuple[str, bytes, str]]


def fields(**overrides: str) -> dict[str, str]:
    return {
        "job_title": "Backend Engineer",
        "company_name": "Acme",
        "posting_url": "https://jobs.acme.test/123",
        **overrides,
    }


def files(resume: bytes | None = PDF, screenshot: bytes | None = None) -> Files:
    out: Files = {}
    if resume is not None:
        out["resume"] = ("resume.pdf", resume, "application/pdf")
    if screenshot is not None:
        out["screenshot"] = ("posting.png", screenshot, "image/png")
    return out


def create(client: TestClient, **overrides: str) -> dict[str, Any]:
    response = client.post(URL, data=fields(**overrides), files=files())
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def stored_file_count(file_store: FileStore) -> int:
    return sum(1 for p in file_store.root.rglob("*") if p.is_file())


def field_errors(response: Any) -> dict[str, str]:
    assert response.status_code == 422, response.text
    return {e["loc"][-1]: e["msg"] for e in response.json()["detail"]}


# --- create (TRK-1) ---------------------------------------------------------------------


def test_create_with_screenshot(client: TestClient, file_store: FileStore) -> None:
    response = client.post(
        URL, data=fields(job_title="  Backend Engineer  "), files=files(screenshot=PNG)
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_title"] == "Backend Engineer"  # trimmed
    assert body["company_name"] == "Acme"
    assert body["posting_url"] == "https://jobs.acme.test/123"
    assert body["resume"]["original_name"] == "resume.pdf"
    assert body["resume"]["content_type"] == "application/pdf"
    assert body["screenshot"]["content_type"] == "image/png"
    assert body["created_at"]

    assert client.get(body["resume"]["url"]).content == PDF
    assert client.get(body["screenshot"]["url"]).content == PNG
    assert stored_file_count(file_store) == 2


def test_create_without_screenshot_accepts_docx(client: TestClient) -> None:
    response = client.post(
        URL,
        data=fields(),
        files={"resume": ("cv.docx", docx(), "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["screenshot"] is None
    assert response.json()["resume"]["content_type"].endswith("wordprocessingml.document")


def test_empty_screenshot_part_counts_as_none(client: TestClient) -> None:
    """Browsers send an empty, unnamed part for a file input left blank."""
    response = client.post(
        URL,
        data=fields(),
        files={**files(), "screenshot": ("", b"", "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["screenshot"] is None


def test_created_at_is_set_by_server(client: TestClient, session: Session) -> None:
    response = client.post(
        URL, data={**fields(), "created_at": "2001-01-01T00:00:00Z"}, files=files()
    )
    assert response.status_code == 201
    created = response.json()["created_at"]
    assert not created.startswith("2001")
    db_now = session.scalar(select(func.now()))
    assert db_now is not None
    stored = session.get(Application, uuid.UUID(response.json()["id"]))
    assert stored is not None
    assert abs((db_now - stored.created_at).total_seconds()) < 60


@pytest.mark.parametrize("missing", ["job_title", "company_name", "posting_url"])
def test_missing_required_field(client: TestClient, missing: str) -> None:
    data = fields()
    del data[missing]
    errors = field_errors(client.post(URL, data=data, files=files()))
    assert set(errors) == {missing}


def test_missing_resume(client: TestClient) -> None:
    errors = field_errors(client.post(URL, data=fields(), files=files(resume=None)))
    assert errors == {"resume": "Choose a file."}


def test_all_errors_reported_together(client: TestClient, file_store: FileStore) -> None:
    response = client.post(
        URL,
        data=fields(job_title=" ", company_name="x" * 201, posting_url="ftp://example.com"),
        files={
            "resume": ("resume.pdf", EXE, "application/pdf"),
            "screenshot": ("s.png", PDF, "image/png"),
        },
    )
    errors = field_errors(response)
    assert set(errors) == {"job_title", "company_name", "posting_url", "resume", "screenshot"}
    assert "http" in errors["posting_url"]
    assert errors["resume"] == "Upload a PDF or DOCX file."
    assert errors["screenshot"] == "Upload a PNG or JPEG or WebP file."
    assert stored_file_count(file_store) == 0


@pytest.mark.parametrize(
    "url", ["not a url", "javascript:alert(1)", "https://", "https://" + "a" * 2050 + ".com"]
)
def test_invalid_url(client: TestClient, url: str) -> None:
    errors = field_errors(client.post(URL, data=fields(posting_url=url), files=files()))
    assert set(errors) == {"posting_url"}


def test_exe_renamed_to_pdf_is_rejected(client: TestClient, session: Session) -> None:
    errors = field_errors(client.post(URL, data=fields(), files=files(resume=EXE)))
    assert set(errors) == {"resume"}
    assert session.scalar(select(func.count()).select_from(Application)) == 0


def test_empty_resume_is_rejected(client: TestClient) -> None:
    errors = field_errors(client.post(URL, data=fields(), files=files(resume=b"")))
    assert set(errors) == {"resume"}


def test_oversized_resume_is_rejected(client: TestClient, file_store: FileStore) -> None:
    too_big = PDF + b"0" * file_store.max_bytes
    errors = field_errors(client.post(URL, data=fields(), files=files(resume=too_big)))
    assert "limit" in errors["resume"]


def test_jpeg_screenshot_accepted(client: TestClient) -> None:
    response = client.post(URL, data=fields(), files=files(screenshot=JPEG))
    assert response.status_code == 201
    assert response.json()["screenshot"]["content_type"] == "image/jpeg"


@pytest.fixture
def failing_commit_client(client: TestClient) -> Iterator[TestClient]:
    """The DB commit fails after the files have been written."""

    def broken_session() -> Iterator[Session]:
        with get_sessionmaker()() as s:

            def fail() -> None:
                raise RuntimeError("database went away")

            s.commit = fail  # type: ignore[method-assign]
            yield s

    client.app.dependency_overrides[get_session] = broken_session  # type: ignore[attr-defined]
    yield client
    del client.app.dependency_overrides[get_session]  # type: ignore[attr-defined]


def test_failed_commit_leaves_no_row_and_no_files(
    failing_commit_client: TestClient, file_store: FileStore, session: Session
) -> None:
    response = failing_commit_client.post(URL, data=fields(), files=files(screenshot=PNG))
    assert response.status_code == 500
    assert stored_file_count(file_store) == 0
    assert session.scalar(select(func.count()).select_from(Application)) == 0
    assert session.scalar(select(func.count()).select_from(StoredFile)) == 0


# --- duplicate check (TRK-1.7) -----------------------------------------------------------


def test_check_url(client: TestClient) -> None:
    check = client.get(f"{URL}/check-url", params={"url": "https://jobs.acme.test/123"}).json()
    assert check == {"duplicate": False, "previous_created_at": None}

    first = create(client)
    check = client.get(
        f"{URL}/check-url", params={"url": "HTTPS://JOBS.ACME.TEST/123/?utm_source=x#top"}
    ).json()
    assert check["duplicate"] is True
    assert check["previous_created_at"] == first["created_at"]

    # Still allowed to save it again.
    assert client.post(URL, data=fields(), files=files()).status_code == 201


# --- list, detail, delete (TRK-2, TRK-3) -------------------------------------------------


def backdate(session: Session, application_id: str, days: int) -> None:
    session.execute(
        text(
            "UPDATE applications SET created_at = now() - make_interval(days => :d) WHERE id = :id"
        ),
        {"d": days, "id": application_id},
    )
    session.commit()


def test_list_newest_first(client: TestClient, session: Session) -> None:
    old = create(client, job_title="Old job")
    new = create(client, job_title="New job")
    backdate(session, old["id"], 3)

    body = client.get(URL).json()
    assert [a["id"] for a in body["items"]] == [new["id"], old["id"]]
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 25


def test_list_search_title_or_company(client: TestClient) -> None:
    create(client, job_title="Data Engineer", company_name="Initech")
    create(client, job_title="Frontend Developer", company_name="Globex")
    create(client, job_title="Platform Engineer", company_name="Data_Corp 100%")

    def titles(q: str) -> list[str]:
        items = client.get(URL, params={"q": q}).json()["items"]
        return sorted(a["job_title"] for a in items)

    assert titles("engineer") == ["Data Engineer", "Platform Engineer"]
    assert titles("GLOBEX") == ["Frontend Developer"]
    assert titles("data") == ["Data Engineer", "Platform Engineer"]
    assert titles("100%") == ["Platform Engineer"]  # % is literal, not a wildcard
    assert titles("dat_ e") == []  # _ is literal too: as a wildcard it would match "Data E..."
    assert titles("data_c") == ["Platform Engineer"]
    assert titles("") == ["Data Engineer", "Frontend Developer", "Platform Engineer"]


def test_list_pagination(client: TestClient) -> None:
    for i in range(27):
        create(client, job_title=f"Job {i}")

    first = client.get(URL).json()
    second = client.get(URL, params={"page": 2}).json()
    assert len(first["items"]) == 25
    assert len(second["items"]) == 2
    assert first["total"] == second["total"] == 27
    ids = {a["id"] for a in first["items"]} | {a["id"] for a in second["items"]}
    assert len(ids) == 27

    assert client.get(URL, params={"page": 0}).status_code == 422
    assert client.get(URL, params={"page_size": 101}).status_code == 422


def test_search_uses_trigram_index(client: TestClient, session: Session) -> None:
    create(client)
    session.execute(text("SET LOCAL enable_seqscan = off"))

    from app.tracker.service import search_expression

    query = select(Application.id).where(
        search_expression().ilike(f"%{escape_like('engineer')}%", escape="\\")
    )
    sql = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    plan = "\n".join(row[0] for row in session.execute(text(f"EXPLAIN {sql}")))
    assert "ix_applications_search" in plan


def test_get_one(client: TestClient) -> None:
    created = create(client)
    response = client.get(f"{URL}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created

    assert client.get(f"{URL}/{uuid.uuid4()}").status_code == 404


def test_delete_removes_row_and_files(
    client: TestClient, file_store: FileStore, session: Session
) -> None:
    response = client.post(URL, data=fields(), files=files(screenshot=PNG))
    created = response.json()
    keep = create(client, job_title="Keep me")
    assert stored_file_count(file_store) == 3

    assert client.delete(f"{URL}/{created['id']}").status_code == 204

    assert client.get(f"{URL}/{created['id']}").status_code == 404
    assert client.get(created["resume"]["url"]).status_code == 404
    assert stored_file_count(file_store) == 1
    assert session.scalar(select(func.count()).select_from(StoredFile)) == 1
    assert client.get(f"{URL}/{keep['id']}").status_code == 200
    assert client.delete(f"{URL}/{created['id']}").status_code == 404


def test_delete_when_file_already_missing(client: TestClient, file_store: FileStore) -> None:
    created = create(client)
    for path in file_store.root.rglob("*.pdf"):
        path.unlink()
    assert client.delete(f"{URL}/{created['id']}").status_code == 204
