import itertools

import pytest

from app.core.llm import LLMInvalidResponseError
from app.core.llm_fake import FakeLLMClient
from app.scraper.schemas import SubScores
from app.scraper.scorer import (
    SYSTEM_PROMPT,
    Weights,
    build_prompt,
    match_skills,
    overall_score,
    score_posting,
)
from tests.scraper.helpers import options, posting, score_json


def test_prompt_contains_search_and_truncated_posting() -> None:
    prompt = build_prompt(options(), posting(description="x" * 100), max_chars=40)
    assert "Desired title: Python Developer" in prompt
    assert "Desired level: Senior" in prompt
    assert "Skills: Python, PostgreSQL, FastAPI, AWS" in prompt
    assert "x" * 40 in prompt and "x" * 41 not in prompt
    assert "Company: Acme" in prompt


def test_overall_score_uses_weights() -> None:
    sub = SubScores(title_fit=10, skills=10, experience=0, level=0, location=0)
    assert overall_score(sub, Weights()) == 60
    assert (
        overall_score(
            SubScores(title_fit=10, skills=10, experience=10, level=10, location=10), Weights()
        )
        == 100
    )
    zero = Weights(title_fit=0, skills=0, experience=0, level=0, location=0)
    assert overall_score(sub, zero) == 40  # all-zero weights fall back to equal weights


def test_match_skills_uses_aliases_and_only_trusts_llm_for_listed_skills() -> None:
    opts = options(skills=["Python", "PostgreSQL", "Kubernetes", "AWS"])
    job = posting(description="Python services on Postgres. Docker experience.")
    matched, missing = match_skills(opts, job, ["Amazon Web Services", "Docker"])
    assert matched == ["Python", "PostgreSQL", "AWS"]
    assert missing == ["Kubernetes"]


def test_more_matching_skills_never_lowers_skills_score() -> None:
    """SCR-4.3 as a property: adding a mentioned skill to a posting never lowers the score."""
    skills = ["Python", "PostgreSQL", "FastAPI", "AWS", "Docker"]
    opts = options(skills=skills)
    for size in range(len(skills) + 1):
        for subset in itertools.combinations(skills, size):
            base = len(match_skills(opts, posting(description=" ".join(subset)), [])[0])
            for extra in set(skills) - set(subset):
                text = " ".join([*subset, extra])
                assert len(match_skills(opts, posting(description=text), [])[0]) >= base


async def test_score_posting_combines_llm_and_computed_skills() -> None:
    llm = FakeLLMClient([score_json(skills=1, matched_skills=["FastAPI"], rationale=" Fits. ")])
    opts = options(skills=["Python", "PostgreSQL", "FastAPI", "AWS"])
    score = await score_posting(
        llm, opts, posting(description="Python and PostgreSQL"), weights=Weights(), max_chars=6000
    )
    # The LLM said skills=1, but 3 of 4 skills match, so the skills score is computed as 8.
    assert score.sub_scores.skills == 8
    assert score.matched_skills == ["Python", "PostgreSQL", "FastAPI"]
    assert score.missing_skills == ["AWS"]
    assert score.rationale == "Fits."
    assert score.overall == overall_score(score.sub_scores, Weights())
    assert SYSTEM_PROMPT


async def test_score_posting_propagates_llm_failure() -> None:
    with pytest.raises(LLMInvalidResponseError):
        await score_posting(
            FakeLLMClient(["not json"]), options(), posting(), weights=Weights(), max_chars=100
        )
