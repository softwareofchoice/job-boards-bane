from collections.abc import Iterator

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import NotFoundError
from app.main import create_app


class Item(BaseModel):
    name: str = Field(min_length=1)
    count: int


router = APIRouter()


@router.post("/test/items")
def create_item(item: Item) -> Item:
    return item


@router.get("/test/missing")
def missing() -> None:
    raise NotFoundError("Nothing here.")


@router.get("/test/boom")
def boom() -> None:
    raise RuntimeError("secret internal detail")


@pytest.fixture
def test_client() -> Iterator[TestClient]:
    app = create_app()
    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_validation_error_lists_each_field(test_client: TestClient) -> None:
    response = test_client.post("/test/items", json={"name": "", "count": "many"})
    assert response.status_code == 422
    fields = {tuple(e["loc"]) for e in response.json()["detail"]}
    assert fields == {("body", "name"), ("body", "count")}


def test_app_error_body(test_client: TestClient) -> None:
    response = test_client.get("/test/missing", headers={"X-Request-ID": "abc123"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Nothing here.", "request_id": "abc123"}
    }
    assert response.headers["x-request-id"] == "abc123"


def test_unexpected_error_hides_details_and_logs_request_id(
    test_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    response = test_client.get("/test/boom")
    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "internal_error"
    assert "secret" not in body["message"]
    request_id = response.headers["x-request-id"]
    assert body["request_id"] == request_id
    logged = [r for r in caplog.records if r.levelname == "ERROR"]
    assert logged and "secret internal detail" in (logged[0].exc_text or "")
    assert getattr(logged[0], "request_id", request_id) == request_id


def test_every_response_gets_a_request_id(test_client: TestClient) -> None:
    first = test_client.get("/test/missing").headers["x-request-id"]
    second = test_client.get("/test/missing").headers["x-request-id"]
    assert first and second and first != second
