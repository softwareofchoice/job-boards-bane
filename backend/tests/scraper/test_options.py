import pytest
from pydantic import ValidationError

from app.scraper.schemas import SearchOptions
from tests.scraper.helpers import options


def test_valid_options() -> None:
    opts = options(location="  ")
    assert opts.location is None
    assert opts.jobs_selected == 3


def test_selected_cannot_exceed_pulled() -> None:
    with pytest.raises(ValidationError, match="Jobs selected can't be more than jobs pulled"):
        options(jobs_pulled=5, jobs_selected=6)
    assert options(jobs_pulled=5, jobs_selected=5).jobs_selected == 5


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_title", ""),
        ("job_title", "x" * 201),
        ("days_since_posting", 0),
        ("days_since_posting", 61),
        ("skills", []),
        ("skills", ["x"] * 31),
        ("skills", ["x" * 51]),
        ("years_experience", -1),
        ("years_experience", 51),
        ("job_level", "wizard"),
        ("jobs_pulled", 0),
        ("jobs_pulled", 101),
        ("jobs_selected", 0),
    ],
)
def test_field_rules(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as info:
        options(**{field: value})
    assert any(err["loc"][0] == field for err in info.value.errors())


def test_round_trips_through_json() -> None:
    opts = options()
    assert SearchOptions.model_validate(opts.model_dump(mode="json")) == opts
