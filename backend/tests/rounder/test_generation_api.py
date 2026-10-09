from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.llm_fake import FakeLLMClient
from app.rounder import resume_doc, sample_resumes
from app.rounder.deps import get_page_measurer, get_posting_renderer
from tests.rounder.helpers import FAKE_PDF, NOTES, POSTING, EstimateMeasurer, router

URL = "/api/rounder/generations"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(autouse=True)
def measurer(client: TestClient) -> Iterator[EstimateMeasurer]:
    fake = EstimateMeasurer()
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    overrides[get_page_measurer] = lambda: fake
    overrides[get_posting_renderer] = lambda: None
    yield fake


@pytest.fixture
def skills(client: TestClient) -> None:
    for note in NOTES:
        response = client.post(
            "/api/rounder/skills",
            json={"skill_name": note.skill_name, "role": note.role, "summary": note.summary},
        )
        assert response.status_code == 201


def form(**overrides: Any) -> dict[str, str]:
    data = {
        "job_title": "Backend Engineer",
        "company_name": "Initech",
        "posting_text": POSTING,
        "posting_url": "",
        "target_pages": "1",
    }
    data.update(overrides)
    return data


def files(template: bytes | None = None) -> dict[str, tuple[str, bytes, str]]:
    data = template if template is not None else sample_resumes.styled()
    return {"template": ("My Resume.docx", data, DOCX_TYPE)}


def field_errors(response: Any) -> dict[str, str]:
    assert response.status_code == 422, response.text
    return {e["loc"][-1]: e["msg"] for e in response.json()["detail"]}


def test_preflight_reports_the_template_and_posting(client: TestClient, skills: None) -> None:
    response = client.post(f"{URL}/preflight", data=form(), files=files())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["experience_found"] is True
    assert [e["bullets"] for e in body["experience_entries"]] == [4, 3, 2]
    assert body["template_pages"] < 1 and body["suggested_target"] == "1"
    assert body["posting_chars"] == len(POSTING)
    assert body["skills_count"] == len(NOTES)
    assert "Experience" in [h["text"] for h in body["headings"]]


@pytest.mark.parametrize(
    "posting", [{"posting_url": "", "posting_text": ""}, {"posting_url": "https://x.test/1"}]
)
def test_both_or_neither_posting_inputs_are_rejected(
    client: TestClient, posting: dict[str, str]
) -> None:
    for path in (f"{URL}/preflight", URL):
        errors = field_errors(client.post(path, data=form(**posting), files=files()))
        assert errors["posting"] == "Provide a job posting URL or paste the description"


def test_every_bad_field_is_reported_together(client: TestClient) -> None:
    errors = field_errors(
        client.post(
            URL,
            data=form(job_title="", company_name="", posting_text="Too short.", target_pages="4"),
            files={"template": ("cv.pdf", FAKE_PDF, "application/pdf")},
        )
    )
    assert set(errors) == {"job_title", "company_name", "posting_text", "target_pages", "template"}
    assert errors["template"] == "Upload a Word (.docx) file."
    assert "at least 200 characters" in errors["posting_text"]


def test_a_posting_url_that_cant_be_read_asks_for_pasted_text(client: TestClient) -> None:
    data = form(posting_text="", posting_url="http://127.0.0.1:9/job")
    errors = field_errors(client.post(f"{URL}/preflight", data=data, files=files()))
    assert "Paste the description instead" in errors["posting_url"]


def test_no_experience_section_lists_headings_then_requires_a_choice(
    client: TestClient, skills: None
) -> None:
    template = sample_resumes.no_experience()
    body = client.post(f"{URL}/preflight", data=form(), files=files(template)).json()
    assert body["experience_found"] is False
    headings = {h["text"]: h["index"] for h in body["headings"]}
    assert "Projects" in headings

    errors = field_errors(client.post(URL, data=form(), files=files(template)))
    assert "experience section" in errors["experience_heading_idx"]

    chosen = form(experience_heading_idx=str(headings["Projects"]))
    body = client.post(f"{URL}/preflight", data=chosen, files=files(template)).json()
    assert body["experience_found"] is True and body["experience_entries"][0]["bullets"] == 7
    assert client.post(URL, data=chosen, files=files(template)).status_code == 202


def test_generation_needs_saved_skills(client: TestClient) -> None:
    body = client.post(f"{URL}/preflight", data=form(), files=files()).json()
    assert body["skills_count"] == 0
    response = client.post(URL, data=form(), files=files())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_skills"


def test_a_full_run_saves_the_resume_report_and_downloads(
    client: TestClient, skills: None, fake_llm: FakeLLMClient
) -> None:
    fake_llm.default = router()
    template = sample_resumes.styled()
    response = client.post(URL, data=form(), files=files(template))
    assert response.status_code == 202, response.text
    started = response.json()

    detail = client.get(f"{URL}/{started['generation_id']}").json()
    assert detail["status"] == "succeeded", detail["error"]
    assert detail["progress"] == {"step": "done"}
    assert detail["final_pages"] == 1 and detail["target_pages"] == "1.0"
    assert detail["model"] == "fake-model"
    report = detail["report"]
    assert report["pages"]["final"] <= 1
    assert {s["skill"]: s["covered_by"] for s in report["posting_skills"]} == {
        "PostgreSQL": "Postgres",
        "Kubernetes": "Kubernetes",
    }
    assert report["entries"][0]["skills_used"] == ["Postgres"]

    assert detail["docx"]["filename"] == "Initech-Backend-Engineer-resume.docx"
    docx = client.get(detail["docx"]["url"])
    assert docx.status_code == 200
    assert 'filename="Initech-Backend-Engineer-resume.docx"' in docx.headers["content-disposition"]
    model = resume_doc.read_resume(docx.content)
    assert model.entries[0].bullets[0].startswith("Designed the Postgres schema")
    assert resume_doc.changes_outside_bullets(template, docx.content, model.heading_idx) == []
    pdf = client.get(detail["pdf"]["url"])
    assert pdf.status_code == 200 and pdf.content == FAKE_PDF
    assert pdf.headers["content-type"] == "application/pdf"

    listed = client.get(URL).json()
    assert [g["id"] for g in listed] == [started["generation_id"]]
    assert listed[0]["status"] == "succeeded"


def test_a_failed_run_keeps_the_error_and_has_no_downloads(
    client: TestClient, skills: None, fake_llm: FakeLLMClient
) -> None:
    fake_llm.default = "not json"
    started = client.post(URL, data=form(), files=files()).json()
    detail = client.get(f"{URL}/{started['generation_id']}").json()
    assert detail["status"] == "failed"
    assert detail["error"]
    assert detail["docx"] is None
    assert client.get(f"{URL}/{started['generation_id']}/resume.docx").status_code == 404


def test_a_posting_url_is_downloaded_by_the_job(
    client: TestClient, skills: None, fake_llm: FakeLLMClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetched: list[str] = []

    async def fake_fetch(url: str, **_: Any) -> str:
        fetched.append(url)
        return POSTING

    monkeypatch.setattr("app.rounder.generation_service.fetch_posting", fake_fetch)
    fake_llm.default = router()
    data = form(posting_text="", posting_url="https://jobs.example.test/1")
    started = client.post(URL, data=data, files=files()).json()
    detail = client.get(f"{URL}/{started['generation_id']}").json()
    assert detail["status"] == "succeeded", detail["error"]
    assert detail["posting_url"] == "https://jobs.example.test/1"
    assert fetched == ["https://jobs.example.test/1"]


def test_unknown_generation_is_404(client: TestClient) -> None:
    assert client.get(f"{URL}/00000000-0000-0000-0000-000000000000").status_code == 404
