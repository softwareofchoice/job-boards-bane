from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.db import get_engine
from app.tracker.models import StatusChange
from app.tracker.status import TRANSITIONS, Status, flow_path
from tests.conftest import alembic_config
from tests.tracker.test_api import URL, create

FLOW = "/api/tracker/status-flow"


def change(client: TestClient, app_id: str, status: str) -> Any:
    return client.post(f"{URL}/{app_id}/status", json={"status": status})


def move(client: TestClient, app_id: str, *statuses: str) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for status in statuses:
        response = change(client, app_id, status)
        assert response.status_code == 200, response.text
        body = response.json()
    return body


# --- transitions (TRK-4.2) -----------------------------------------------------------------


def test_the_transitions_are_the_requested_flow() -> None:
    assert TRANSITIONS == {
        Status.APPLIED: (Status.INTERVIEWING, Status.REJECTED),
        Status.INTERVIEWING: (Status.OFFER, Status.REJECTED),
        Status.OFFER: (),
        Status.REJECTED: (),
    }


@pytest.mark.parametrize(
    ("history", "path"),
    [
        ([], ("applied", "applied", "applied")),
        (["applied"], ("applied", "applied", "applied")),
        (["applied", "rejected"], ("applied", "rejected", "rejected")),
        (["applied", "interviewing"], ("applied", "interviewing", "interviewing")),
        (["applied", "interviewing", "offer"], ("applied", "interviewing", "offer")),
    ],
)
def test_histories_become_three_stage_paths(history: list[str], path: tuple[str, ...]) -> None:
    assert flow_path([Status(s) for s in history]) == path


# --- API (TRK-4) ---------------------------------------------------------------------------


def test_a_new_application_is_applied_with_one_history_entry(client: TestClient) -> None:
    created = create(client)
    assert created["status"] == "applied"
    assert created["allowed_next"] == ["interviewing", "rejected"]
    assert created["status_history"] == [
        {"from_status": None, "to_status": "applied", "changed_at": created["created_at"]}
    ]


@pytest.mark.parametrize(
    "path",
    [["interviewing", "offer"], ["interviewing", "rejected"], ["rejected"]],
)
def test_every_allowed_path_is_recorded_in_order(client: TestClient, path: list[str]) -> None:
    created = create(client)
    body = move(client, created["id"], *path)
    assert body["status"] == path[-1]
    assert body["allowed_next"] == []
    steps = [(c["from_status"], c["to_status"]) for c in body["status_history"]]
    assert steps == list(zip([None, "applied", *path[:-1]], ["applied", *path], strict=True))
    times = [c["changed_at"] for c in body["status_history"]]
    assert times == sorted(times)
    assert client.get(f"{URL}/{created['id']}").json() == body


@pytest.mark.parametrize(
    ("before", "attempt", "message"),
    [
        ([], "offer", "From Applied you can move to Interviewing or Rejected."),
        ([], "applied", "From Applied you can move to Interviewing or Rejected."),
        (["interviewing"], "applied", "From Interviewing you can move to Offer or Rejected."),
        (["rejected"], "interviewing", "Rejected is final."),
        (["interviewing", "offer"], "rejected", "Offer is final."),
    ],
)
def test_other_changes_are_refused_and_change_nothing(
    client: TestClient, before: list[str], attempt: str, message: str
) -> None:
    created = create(client)
    expected = move(client, created["id"], *before) if before else created
    response = change(client, created["id"], attempt)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "invalid_status_change"
    assert message in error["message"]
    assert error["allowed"] == [s.value for s in TRANSITIONS[Status(expected["status"])]]
    assert client.get(f"{URL}/{created['id']}").json() == expected


def test_an_unknown_status_is_a_validation_error(client: TestClient) -> None:
    created = create(client)
    assert change(client, created["id"], "ghosted").status_code == 422


def test_undo_removes_the_latest_change(client: TestClient) -> None:
    created = create(client)
    move(client, created["id"], "interviewing", "rejected")
    response = client.delete(f"{URL}/{created['id']}/status/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "interviewing"
    assert [c["to_status"] for c in body["status_history"]] == ["applied", "interviewing"]
    assert body["allowed_next"] == ["offer", "rejected"]
    # And a different choice can be made now.
    assert move(client, created["id"], "offer")["status"] == "offer"


def test_the_initial_status_cant_be_undone(client: TestClient) -> None:
    created = create(client)
    response = client.delete(f"{URL}/{created['id']}/status/latest")
    assert response.status_code == 409
    assert (
        client.get(f"{URL}/{created['id']}").json()["status_history"] == created["status_history"]
    )


def test_unknown_application_is_404(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert change(client, missing, "interviewing").status_code == 404
    assert client.delete(f"{URL}/{missing}/status/latest").status_code == 404


def test_the_list_shows_and_filters_by_status(client: TestClient) -> None:
    applied = create(client, job_title="Applied one")
    interviewing = create(client, job_title="Interviewing one")
    move(client, interviewing["id"], "interviewing")
    rows = client.get(URL).json()["items"]
    assert {r["job_title"]: r["status"] for r in rows} == {
        "Applied one": "applied",
        "Interviewing one": "interviewing",
    }
    filtered = client.get(URL, params={"status": "interviewing"}).json()
    assert [r["id"] for r in filtered["items"]] == [interviewing["id"]]
    assert filtered["total"] == 1
    both = client.get(URL, params={"status": "applied", "q": "Applied"}).json()
    assert [r["id"] for r in both["items"]] == [applied["id"]]
    assert client.get(URL, params={"status": "ghosted"}).status_code == 422


def test_deleting_an_application_deletes_its_history(client: TestClient, session: Session) -> None:
    created = create(client)
    move(client, created["id"], "interviewing")
    assert client.delete(f"{URL}/{created['id']}").status_code == 204
    assert session.scalar(select(func.count()).select_from(StatusChange)) == 0


# --- flow (TRK-5.1) ------------------------------------------------------------------------


def test_the_flow_counts_each_path(client: TestClient) -> None:
    assert client.get(FLOW).json() == {"total": 0, "paths": []}
    for path in (
        [],
        [],
        ["rejected"],
        ["interviewing"],
        ["interviewing", "offer"],
        ["interviewing", "offer"],
        ["interviewing", "offer"],
    ):
        move(client, create(client)["id"], *path)
    flow = client.get(FLOW).json()
    assert flow["total"] == 7
    assert flow["paths"] == [
        {"statuses": ["applied", "interviewing", "offer"], "count": 3},
        {"statuses": ["applied", "applied", "applied"], "count": 2},
        {"statuses": ["applied", "interviewing", "interviewing"], "count": 1},
        {"statuses": ["applied", "rejected", "rejected"], "count": 1},
    ]


# --- migration (TRK-4.1) -------------------------------------------------------------------


def test_the_migration_gives_existing_applications_an_initial_status() -> None:
    config = alembic_config()
    try:
        command.downgrade(config, "0004")
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO stored_files (id, category, relative_path, original_name, "
                    "content_type, size_bytes, sha256) VALUES ('00000000-0000-0000-0000-"
                    "000000000001', 'resume', 'r/1/a.pdf', 'a.pdf', 'application/pdf', 1, 'x')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO applications (job_title, company_name, posting_url, "
                    "posting_url_normalized, resume_file_id, created_at) VALUES ('T', 'C', "
                    "'https://x.test', 'https://x.test', '00000000-0000-0000-0000-000000000001', "
                    "'2026-01-02T03:04:05Z')"
                )
            )
        command.upgrade(config, "head")
        with get_engine().begin() as conn:
            status = conn.execute(text("SELECT status FROM applications")).scalar_one()
            history = conn.execute(
                text(
                    "SELECT c.from_status, c.to_status, c.changed_at = a.created_at "
                    "FROM application_status_changes c JOIN applications a "
                    "ON a.id = c.application_id"
                )
            ).all()
        assert status == "applied"
        assert [tuple(row) for row in history] == [(None, "applied", True)]
    finally:
        command.upgrade(config, "head")
