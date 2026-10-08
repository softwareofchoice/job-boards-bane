import json

from app.core.llm_fake import FakeLLMClient
from app.rounder.matching import EntrySkills
from app.rounder.rewrite import (
    EntryJob,
    cut_budgets,
    fit_to_budget,
    initial_total,
    made_up_facts,
    rewrite_entry,
    share_budget,
)
from tests.rounder.helpers import NOTES, rewritten

ORIGINAL = [
    "Built and maintained REST APIs in Python serving the analytics dashboard.",
    "Cut page load time of the main dashboard by 40% by caching query results.",
]
SOURCES = "\n".join([*ORIGINAL, "Postgres: Designed the Postgres schema for 3 teams."])


def test_new_numbers_are_caught_and_known_ones_allowed() -> None:
    assert made_up_facts(["Cut load time by 40% for 3 teams."], SOURCES) == []
    assert made_up_facts(["Cut load time by 55% in 2 weeks."], SOURCES) == ["55", "2"]


def test_new_names_are_caught_but_a_bullet_starting_word_is_not() -> None:
    assert made_up_facts(["Designed the Postgres schema."], SOURCES) == []
    assert made_up_facts(["Led the Postgres work at Globex Corporation."], SOURCES) == [
        "Globex",
        "Corporation",
    ]
    # A new sentence starts with a capital too.
    assert made_up_facts(["Built APIs. Designed schemas."], SOURCES) == []


def test_technologies_slipped_in_lower_case_are_caught() -> None:
    assert made_up_facts(["moved services to kubernetes"], SOURCES) == ["kubernetes"]
    assert made_up_facts(["helped the team go live"], SOURCES) == []


def test_the_total_scales_with_the_target_within_limits() -> None:
    assert initial_total(1000, 2.0, 1.0) == 500
    assert initial_total(1000, 1.0, 3.0) == 1250
    assert initial_total(1000, 0.0, 1.0) == 1000


def test_extra_space_goes_to_relevant_entries_and_others_keep_theirs() -> None:
    assert share_budget([300, 300, 100], [4, 0, 0], 900) == [500, 300, 100]
    assert share_budget([300, 100], [0, 0], 800) == [600, 200]


def test_less_space_is_taken_mostly_from_irrelevant_entries() -> None:
    budgets = share_budget([300, 300, 100], [4, 0, 0], 500)
    assert budgets[0] > 500 * 3 / 7 > budgets[1]
    assert budgets[2] >= 80


def test_cuts_come_from_the_least_relevant_entry_first() -> None:
    budgets = cut_budgets([400, 400], [400, 400], [3, 0], 150)
    assert budgets == [400, 250]
    # Never under the minimum, however much is asked for.
    assert cut_budgets([400, 100], [400, 100], [3, 0], 10_000) == [80, 80]


def test_fit_to_budget_drops_trailing_bullets_but_keeps_one() -> None:
    assert fit_to_budget(["a" * 50, "b" * 50, "c" * 50], 100) == ["a" * 50, "b" * 50]
    assert fit_to_budget(["a" * 500], 100) == ["a" * 500]


def job(budget: int = 300) -> EntryJob:
    skills = EntrySkills(role=NOTES[0].role, notes=NOTES[:2], wanted=["PostgreSQL"], relevance=2)
    return EntryJob("Senior Software Engineer, Northwind Analytics", ORIGINAL, skills, budget)


async def test_a_clean_rewrite_is_used_with_only_known_skill_names() -> None:
    llm = FakeLLMClient(
        [rewritten(["Designed the Postgres schema and tuned indexes."], ["postgres", "Docker"])]
    )
    result = await rewrite_entry(llm, job(), "Backend Engineer", "Initech")
    assert result.bullets == ["Designed the Postgres schema and tuned indexes."]
    assert result.skills_used == ["Postgres"]
    assert result.kept_original_reason is None
    prompt = llm.prompts[0]
    assert "TARGET JOB: Backend Engineer at Initech" in prompt
    assert "- Postgres: Designed the Postgres schema" in prompt
    assert "at most 300 characters" in prompt


async def test_made_up_facts_get_one_retry() -> None:
    llm = FakeLLMClient(
        [
            rewritten(["Cut costs by 70% at Globex."]),
            rewritten(["Built internal FastAPI services for report generation."], ["FastAPI"]),
        ]
    )
    result = await rewrite_entry(llm, job(), "Backend Engineer", "Initech")
    assert result.bullets == ["Built internal FastAPI services for report generation."]
    assert "70, Globex" in llm.prompts[1]


async def test_a_new_employer_twice_keeps_the_original_bullets() -> None:
    llm = FakeLLMClient(default=rewritten(["Led the platform team at Globex Corporation."]))
    result = await rewrite_entry(llm, job(), "Backend Engineer", "Initech")
    assert result.bullets == ORIGINAL
    assert result.kept_original_reason and "Globex" in result.kept_original_reason
    assert len(llm.prompts) == 2


async def test_an_unusable_reply_keeps_the_original_bullets() -> None:
    llm = FakeLLMClient(default=json.dumps({"wrong": True}))
    result = await rewrite_entry(llm, job(), "Backend Engineer", "Initech")
    assert result.bullets == ORIGINAL
    assert result.kept_original_reason == "The local model's reply couldn't be used."


def test_singular_and_plural_of_a_known_name_are_allowed() -> None:
    assert made_up_facts(["Designed a REST API for reports."], SOURCES) == []
