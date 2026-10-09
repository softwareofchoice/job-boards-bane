import pytest

from app.core.llm_fake import FakeLLMClient
from app.rounder.matching import (
    PostingSkill,
    assign,
    extract_posting_skills,
    match_roles,
    match_skills,
)
from tests.rounder.helpers import FABRIKAM, NORTHWIND, NOTES, pairs, posting_skills

HEADERS = [
    "Senior Software Engineer, Northwind Analytics · Mar 2021 \u2013 Present",
    "Software Engineer, Fabrikam Logistics · Jun 2018 \u2013 Feb 2021",
    "Junior Developer, Contoso Retail · Aug 2016 \u2013 May 2018",
]


async def test_extraction_puts_required_first_and_drops_duplicates() -> None:
    llm = FakeLLMClient([posting_skills(["Python", "postgres", " "], ["PostgreSQL", "Terraform"])])
    skills = await extract_posting_skills(llm, "posting text")
    assert [(s.skill, s.kind) for s in skills] == [
        ("Python", "required"),
        ("postgres", "required"),
        ("Terraform", "preferred"),
    ]
    assert "POSTING:\nposting text" in llm.prompts[0]


async def test_names_and_aliases_match_without_the_llm() -> None:
    skills = [PostingSkill("PostgreSQL", "required"), PostingSkill("K8s", "required")]
    llm = FakeLLMClient()  # no reply queued: a call would fail the test
    await match_skills(llm, skills, ["Postgres", "Kubernetes"])
    assert [s.covered_by for s in skills] == [["Postgres"], ["Kubernetes"]]
    assert llm.prompts == []


async def test_a_posting_phrase_that_mentions_a_saved_skill_matches() -> None:
    skills = [PostingSkill("Experience with Kubernetes in production", "preferred")]
    await match_skills(FakeLLMClient(), skills, ["Kubernetes"])
    assert skills[0].covered_by == ["Kubernetes"]


async def test_llm_synonyms_are_used_and_invented_names_are_ignored() -> None:
    skills = [PostingSkill("Container orchestration", "required"), PostingSkill("Go", "preferred")]
    llm = FakeLLMClient(
        [
            pairs(
                ("Container orchestration", "Kubernetes"),
                ("Go", "Golang"),  # "Golang" isn't a saved skill
                ("Haskell", "Rust"),  # "Haskell" isn't in the posting
            )
        ]
    )
    await match_skills(llm, skills, ["Kubernetes", "Rust"])
    assert skills[0].covered_by == ["Kubernetes"]
    assert skills[1].covered_by == []
    assert "POSTING SKILLS:\n- Container orchestration\n- Go" in llm.prompts[0]
    assert "SAVED SKILLS:\n- Kubernetes\n- Rust" in llm.prompts[0]


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (NORTHWIND, 0),
        (FABRIKAM, 1),
        ("Junior Developer, Contoso", 2),
        ("Barista at Central Perk", None),
    ],
)
def test_roles_match_the_best_entry_above_the_threshold(role: str, expected: int | None) -> None:
    assert match_roles([role], HEADERS)[role] == expected


def test_assign_groups_notes_by_entry_with_relevance() -> None:
    posting = [
        PostingSkill("PostgreSQL", "required", ["Postgres"]),
        PostingSkill("Kubernetes", "required", ["Kubernetes"]),
        PostingSkill("FastAPI", "preferred", ["FastAPI"]),
        PostingSkill("Terraform", "preferred", []),
    ]
    matched = assign(posting, NOTES, HEADERS)
    northwind, fabrikam = matched.entries[0], matched.entries[1]
    assert [n.skill_name for n in northwind.notes] == ["Postgres", "FastAPI"]
    assert northwind.relevance == 3 and northwind.wanted == ["PostgreSQL", "FastAPI"]
    assert fabrikam.relevance == 2 and fabrikam.wanted == ["Kubernetes"]
    assert 2 not in matched.entries
    assert matched.unmatched_roles == ["Open source maintainer"]
