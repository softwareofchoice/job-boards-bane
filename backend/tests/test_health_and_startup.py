import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.db import get_engine
from app.core.llm import LLMModelMissingError, LLMUnavailableError
from app.core.llm_fake import FakeLLMClient

DOWN_URL = "postgresql+psycopg://bane:hunter2@localhost:1/bane"


@pytest.mark.parametrize("db_up", [True, False])
@pytest.mark.parametrize("llm_up", [True, False])
def test_health(client: TestClient, fake_llm: FakeLLMClient, db_up: bool, llm_up: bool) -> None:
    if not db_up:
        client.app.dependency_overrides[get_engine] = lambda: create_engine(  # type: ignore[attr-defined]
            DOWN_URL, connect_args={"connect_timeout": 1}
        )
    if not llm_up:
        fake_llm.check_error = LLMUnavailableError("Can't reach the local LLM server.")

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["db"] == ("ok" if db_up else "error")
    assert body["llm"] == ("ok" if llm_up else "error")
    assert body["model"] == fake_llm.model
    assert (body["llm_message"] is None) == llm_up


def test_health_reports_missing_model(client: TestClient, fake_llm: FakeLLMClient) -> None:
    fake_llm.check_error = LLMModelMissingError("Run `ollama pull x`.")
    body = client.get("/api/health").json()
    assert body["llm"] == "error"
    assert "ollama pull" in body["llm_message"]


def test_startup_exits_when_database_is_down(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app import main

    monkeypatch.setattr(
        main, "get_engine", lambda: create_engine(DOWN_URL, connect_args={"connect_timeout": 1})
    )
    with pytest.raises(SystemExit) as exit_info:
        main.startup()

    assert exit_info.value.code == 1
    message = caplog.text
    assert "localhost:1/bane" in message
    assert "hunter2" not in message
