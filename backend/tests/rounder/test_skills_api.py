from typing import Any

from fastapi.testclient import TestClient

URL = "/api/rounder/skills"


def skill(**overrides: Any) -> dict[str, Any]:
    data = {
        "skill_name": "PostgreSQL",
        "role": "Software Engineer at Acme",
        "summary": "Designed the reporting schema and tuned slow queries.",
    }
    data.update(overrides)
    return data


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post(URL, json=skill(**overrides))
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def field_errors(response: Any) -> dict[str, str]:
    return {e["loc"][-1]: e["msg"] for e in response.json()["detail"]}


def test_create_saves_the_skill_with_timestamps(client: TestClient) -> None:
    created = create(client, skill_name="  PostgreSQL ")
    assert created["skill_name"] == "PostgreSQL"
    assert created["created_at"] and created["updated_at"]
    assert client.get(f"{URL}/{created['id']}").json() == created


def test_every_field_is_required_and_limited(client: TestClient) -> None:
    response = client.post(URL, json=skill(skill_name="", role="r" * 201, summary="s" * 1001))
    assert response.status_code == 422
    assert set(field_errors(response)) == {"skill_name", "role", "summary"}


def test_duplicate_name_and_role_ignoring_case_is_refused_with_the_existing_id(
    client: TestClient,
) -> None:
    first = create(client)
    response = client.post(
        URL, json=skill(skill_name="postgresql", role="SOFTWARE ENGINEER AT ACME")
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "duplicate_skill"
    assert error["existing_id"] == first["id"]


def test_same_skill_in_another_role_is_allowed(client: TestClient) -> None:
    create(client)
    create(client, role="Freelance")


def test_list_is_ordered_by_role_and_can_be_filtered(client: TestClient) -> None:
    create(client, skill_name="Python", role="b role")
    create(client, skill_name="Go", role="A role")
    create(client, skill_name="Docker", role="b role")
    names = [(s["role"], s["skill_name"]) for s in client.get(URL).json()]
    assert names == [("A role", "Go"), ("b role", "Docker"), ("b role", "Python")]
    filtered = client.get(URL, params={"role": "B ROLE"}).json()
    assert [s["skill_name"] for s in filtered] == ["Docker", "Python"]


def test_roles_are_distinct_ignoring_case(client: TestClient) -> None:
    create(client, skill_name="Python", role="Engineer at Acme")
    create(client, skill_name="Go", role="engineer at acme")
    create(client, skill_name="Rust", role="Freelance")
    assert client.get(f"{URL}/roles").json() == ["Engineer at Acme", "Freelance"]


def test_update_changes_the_entry(client: TestClient) -> None:
    created = create(client)
    response = client.put(f"{URL}/{created['id']}", json=skill(summary="New summary."))
    assert response.status_code == 200
    assert response.json()["summary"] == "New summary."
    # Changing only the case of its own name isn't a duplicate.
    assert client.put(f"{URL}/{created['id']}", json=skill(skill_name="postgresql")).is_success


def test_update_into_an_existing_entry_is_refused(client: TestClient) -> None:
    first = create(client)
    second = create(client, skill_name="Python")
    response = client.put(f"{URL}/{second['id']}", json=skill())
    assert response.status_code == 409
    assert response.json()["error"]["existing_id"] == first["id"]


def test_delete_removes_the_entry(client: TestClient) -> None:
    created = create(client)
    assert client.delete(f"{URL}/{created['id']}").status_code == 204
    assert client.get(f"{URL}/{created['id']}").status_code == 404
    assert client.delete(f"{URL}/{created['id']}").status_code == 404
