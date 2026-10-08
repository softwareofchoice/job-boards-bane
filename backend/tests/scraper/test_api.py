import csv
import io
import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.llm_fake import FakeLLMClient
from app.scraper.deps import get_job_source
from app.scraper.pipeline import RUN_LOCK
from app.scraper.schemas import RawPosting
from app.scraper.sources.fake import FakeJobSource
from tests.scraper.helpers import options, posting, score_json

URL = "/api/scraper/runs"
TODAY = datetime.now(UTC).date()


def body(**overrides: Any) -> dict[str, Any]:
    return options(**overrides).model_dump(mode="json")


@pytest.fixture
def source(client: TestClient) -> Iterator[FakeJobSource]:
    fake = FakeJobSource(postings=[])
    client.app.dependency_overrides[get_job_source] = lambda: fake  # type: ignore[attr-defined]
    yield fake


def title_score(prompt: str) -> str:
    """A fake LLM reply whose title_fit comes from the posting title, e.g. "Job 7" -> 7."""
    title = prompt.split("Title: ", 1)[1].splitlines()[0]
    fit = int(title.rsplit(" ", 1)[-1]) if title.rsplit(" ", 1)[-1].isdigit() else 5
    return score_json(title_fit=min(fit, 10), rationale=f"Scored {title}.")


def jobs(n: int, **overrides: Any) -> list[RawPosting]:
    return [
        posting(
            title=f"Job {i}",
            company=f"Co {i}",
            url=f"https://x.test/{i}",
            posted_at=TODAY - timedelta(days=1),
            **overrides,
        )
        for i in range(n)
    ]


def start(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post(URL, json=body(**overrides))
    assert response.status_code == 202, response.text
    result: dict[str, Any] = response.json()
    return result


def test_run_scores_ranks_and_selects_top_x(
    client: TestClient, source: FakeJobSource, fake_llm: FakeLLMClient
) -> None:
    source.postings = jobs(6)
    fake_llm.default = title_score

    started = start(client, jobs_pulled=6, jobs_selected=3)
    run = client.get(f"{URL}/{started['run_id']}").json()

    assert run["status"] == "succeeded"
    assert run["pulled_count"] == 6
    assert run["selected_count"] == 3
    assert run["progress"] == {"step": "done", "done": 6, "total": 6}
    assert run["source"] == "fake"
    assert run["model"] == "fake-model"
    titles = [p["title"] for p in run["postings"]]
    assert titles == ["Job 5", "Job 4", "Job 3"]
    top = run["postings"][0]
    assert top["rank"] == 1 and top["selected"] is True
    assert top["sub_scores"]["title_fit"] == 5
    assert top["matched_skills"] == ["Python", "PostgreSQL"]
    assert top["missing_skills"] == ["FastAPI", "AWS"]
    assert top["rationale"] == "Scored Job 5."
    assert len(fake_llm.prompts) == 6

    everything = client.get(f"{URL}/{started['run_id']}", params={"all": "true"}).json()
    assert len(everything["postings"]) == 6
    assert [p["rank"] for p in everything["postings"]] == [1, 2, 3, 4, 5, 6]


def test_ties_go_to_the_newest_posting(
    client: TestClient, source: FakeJobSource, fake_llm: FakeLLMClient
) -> None:
    source.postings = [
        posting(title="Old", company="A", posted_at=TODAY - timedelta(days=5)),
        posting(title="Unknown date", company="B", posted_at=None),
        posting(title="New", company="C", posted_at=TODAY),
    ]
    fake_llm.default = score_json()
    run = client.get(f"{URL}/{start(client, jobs_selected=2)['run_id']}").json()
    assert [p["title"] for p in run["postings"]] == ["New", "Old"]


def test_failed_scoring_excludes_posting_but_run_finishes(
    client: TestClient, source: FakeJobSource, fake_llm: FakeLLMClient
) -> None:
    source.postings = jobs(3)
    fake_llm.queue(score_json(title_fit=9), "not json", score_json(title_fit=2))

    run_id = start(client, jobs_pulled=3, jobs_selected=3)["run_id"]
    run = client.get(f"{URL}/{run_id}", params={"all": "true"}).json()

    assert run["status"] == "succeeded"
    assert run["selected_count"] == 2
    failed = next(p for p in run["postings"] if p["title"] == "Job 1")
    assert failed["score"] is None and failed["rank"] is None and failed["selected"] is False
    assert failed["score_error"]
    assert run["postings"][-1]["title"] == "Job 1"  # unscored sort last


def test_duplicates_and_old_postings_are_dropped(
    client: TestClient, source: FakeJobSource, fake_llm: FakeLLMClient
) -> None:
    source.postings = [
        posting(title="Dev", company="Acme", description="short"),
        posting(title="dev", company="ACME", description="the longer description"),
        posting(title="Old", company="Globex", posted_at=TODAY - timedelta(days=30)),
        posting(title="Fresh", company="Initech", posted_at=TODAY),
    ]
    source.stopped_reason = "exhausted"
    fake_llm.default = score_json()

    run = client.get(
        f"{URL}/{start(client, days_since_posting=7)['run_id']}", params={"all": "true"}
    ).json()

    assert run["pulled_count"] == 2
    assert run["stopped_reason"] == "exhausted"
    # The duplicate with the longer description is the one kept.
    assert sorted(p["title"] for p in run["postings"]) == ["Fresh", "dev"]
    dev = next(p for p in run["postings"] if p["title"] == "dev")
    assert dev["description"] == "the longer description"


def test_source_is_asked_for_jobs_pulled(client: TestClient, source: FakeJobSource) -> None:
    start(client, jobs_pulled=25, jobs_selected=5)
    assert source.calls[0][1] == 25


def test_source_failure_fails_the_run(client: TestClient, fake_llm: FakeLLMClient) -> None:
    class Broken(FakeJobSource):
        async def search(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("browser crashed")

    client.app.dependency_overrides[get_job_source] = lambda: Broken()  # type: ignore[attr-defined]
    run = client.get(f"{URL}/{start(client)['run_id']}").json()
    assert run["status"] == "failed"
    assert run["error"] == "browser crashed"
    assert not RUN_LOCK.locked()


def test_only_one_search_at_a_time(client: TestClient, source: FakeJobSource) -> None:
    assert RUN_LOCK.acquire(blocking=False)
    try:
        response = client.post(URL, json=body())
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "search_running"
    finally:
        RUN_LOCK.release()
    assert client.post(URL, json=body()).status_code == 202
    assert not RUN_LOCK.locked()


def test_invalid_options_are_rejected(client: TestClient, source: FakeJobSource) -> None:
    response = client.post(URL, json=body() | {"jobs_pulled": 5, "jobs_selected": 6})
    assert response.status_code == 422
    assert "Jobs selected can't be more than jobs pulled" in json.dumps(response.json())
    assert not RUN_LOCK.locked()


def test_list_runs_newest_first(client: TestClient, source: FakeJobSource) -> None:
    first = start(client, job_title="First")
    second = start(client, job_title="Second")
    runs = client.get(URL).json()
    assert [r["id"] for r in runs] == [second["run_id"], first["run_id"]]
    assert runs[0]["options"]["job_title"] == "Second"
    assert runs[0]["status"] == "succeeded"


def test_csv_export_matches_saved_rows(
    client: TestClient, source: FakeJobSource, fake_llm: FakeLLMClient
) -> None:
    source.postings = jobs(4)
    fake_llm.default = title_score
    run_id = start(client, job_title="Python Developer", jobs_pulled=4, jobs_selected=2)["run_id"]

    response = client.get(f"{URL}/{run_id}/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="jobs-python-developer-' in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert [r["title"] for r in rows] == ["Job 3", "Job 2"]
    assert rows[0]["rank"] == "1"
    assert rows[0]["matched_skills"] == "Python; PostgreSQL"

    everything = client.get(f"{URL}/{run_id}/export.csv", params={"all": "true"})
    assert len(list(csv.DictReader(io.StringIO(everything.content.decode("utf-8-sig"))))) == 4


def test_delete_run(client: TestClient, source: FakeJobSource) -> None:
    run_id = start(client)["run_id"]
    assert client.delete(f"{URL}/{run_id}").status_code == 204
    assert client.get(f"{URL}/{run_id}").status_code == 404
    assert client.delete(f"{URL}/{uuid.uuid4()}").status_code == 404
