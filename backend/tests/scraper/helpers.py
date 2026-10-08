import json
from typing import Any

from app.scraper.schemas import JobLevel, RawPosting, SearchOptions


def options(**overrides: Any) -> SearchOptions:
    data: dict[str, Any] = {
        "job_title": "Python Developer",
        "location": "Austin, TX",
        "days_since_posting": 7,
        "skills": ["Python", "PostgreSQL", "FastAPI", "AWS"],
        "years_experience": 5,
        "job_level": JobLevel.SENIOR,
        "jobs_pulled": 10,
        "jobs_selected": 3,
    }
    data.update(overrides)
    return SearchOptions.model_validate(data)


def posting(**overrides: Any) -> RawPosting:
    data: dict[str, Any] = {
        "title": "Python Developer",
        "company": "Acme",
        "location": "Austin, TX",
        "url": "https://jobs.example.test/1",
        "description": "Python and PostgreSQL.",
    }
    data.update(overrides)
    return RawPosting.model_validate(data)


def score_json(**overrides: Any) -> str:
    data: dict[str, Any] = {
        "title_fit": 8,
        "skills": 5,
        "experience": 7,
        "level": 6,
        "location": 10,
        "matched_skills": [],
        "missing_skills": [],
        "rationale": "Good fit.",
    }
    data.update(overrides)
    return json.dumps(data)
