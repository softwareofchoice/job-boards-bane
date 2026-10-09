"""Finding the posting's skills and matching them to saved skills and resume entries
(RND-3.1 to RND-3.3)."""

from dataclasses import dataclass, field
from typing import Literal

from rapidfuzz import fuzz

from app.core.llm import LLM
from app.core.skills import normalize_skill, same_skill, text_mentions_skill
from app.rounder import prompts
from app.rounder.schemas import PostingSkills, SkillPairs

ROLE_MATCH_THRESHOLD = 80
WEIGHTS = {"required": 2, "preferred": 1}
Kind = Literal["required", "preferred"]


@dataclass(frozen=True)
class SkillNote:
    """A saved skill entry as the pipeline sees it."""

    skill_name: str
    role: str
    summary: str


@dataclass
class PostingSkill:
    skill: str
    kind: Kind
    covered_by: list[str] = field(default_factory=list)  # saved skill names


@dataclass
class EntrySkills:
    """What gets written into one experience entry."""

    role: str | None = None
    notes: list[SkillNote] = field(default_factory=list)
    wanted: list[str] = field(default_factory=list)  # posting skills, most important first
    relevance: int = 0


@dataclass
class Matching:
    posting_skills: list[PostingSkill]
    entries: dict[int, EntrySkills]
    unmatched_roles: list[str]


def posting_skill_list(found: PostingSkills) -> list[PostingSkill]:
    """Required first; a skill listed as both counts as required; duplicates dropped."""
    result: list[PostingSkill] = []
    for kind, names in (("required", found.required), ("preferred", found.preferred)):
        for name in names:
            name = name.strip()
            if name and not any(same_skill(name, s.skill) for s in result):
                result.append(PostingSkill(name, kind))  # type: ignore[arg-type]
    return result


async def extract_posting_skills(llm: LLM, posting_text: str) -> list[PostingSkill]:
    found = await llm.complete_json(
        prompts.extract_skills(posting_text), PostingSkills, system=prompts.EXTRACT_SYSTEM
    )
    return posting_skill_list(found)


def _names_match(posting_skill: str, saved: str) -> bool:
    return same_skill(posting_skill, saved) or text_mentions_skill(posting_skill, saved)


async def match_skills(llm: LLM, posting: list[PostingSkill], saved_names: list[str]) -> None:
    """Fill in `covered_by`: by normalised name and aliases first, then synonyms from the LLM
    for what's left. Pairs naming a skill that isn't in either list are ignored (RND-3.2)."""
    names = sorted({n for n in saved_names}, key=str.lower)
    for skill in posting:
        skill.covered_by = [n for n in names if _names_match(skill.skill, n)]
    used = {normalize_skill(n) for s in posting for n in s.covered_by}
    open_posting = [s for s in posting if not s.covered_by]
    open_saved = [n for n in names if normalize_skill(n) not in used]
    if not open_posting or not open_saved:
        return
    reply = await llm.complete_json(
        prompts.pair_skills([s.skill for s in open_posting], open_saved),
        SkillPairs,
        system=prompts.PAIR_SYSTEM,
    )
    by_posting = {normalize_skill(s.skill): s for s in open_posting}
    by_saved = {normalize_skill(n): n for n in open_saved}
    for pair in reply.pairs:
        wanted = by_posting.get(normalize_skill(pair.posting_skill))
        saved = by_saved.get(normalize_skill(pair.saved_skill))
        if wanted is not None and saved is not None and saved not in wanted.covered_by:
            wanted.covered_by.append(saved)


def match_roles(roles: list[str], headers: list[str]) -> dict[str, int | None]:
    """Each role's best-matching experience entry, or None below the threshold (RND-3.3)."""
    result: dict[str, int | None] = {}
    for role in roles:
        best, best_score = None, 0.0
        for i, header in enumerate(headers):
            score = fuzz.token_set_ratio(role.lower(), header.lower())
            if score > best_score:
                best, best_score = i, score
        result[role] = best if best_score >= ROLE_MATCH_THRESHOLD else None
    return result


def assign(posting: list[PostingSkill], notes: list[SkillNote], headers: list[str]) -> Matching:
    """Group matched skill notes by experience entry, with each entry's relevance."""
    roles: dict[str, str] = {}
    for note in notes:
        roles.setdefault(note.role.lower(), note.role)
    role_entry = match_roles(list(roles.values()), headers)
    entries: dict[int, EntrySkills] = {}
    for role, entry_no in role_entry.items():
        if entry_no is not None:
            entries.setdefault(entry_no, EntrySkills(role=role))

    for skill in posting:  # posting order is importance order: required first
        for note in notes:
            entry_no = role_entry.get(roles[note.role.lower()])
            if entry_no is None or not any(
                same_skill(note.skill_name, n) for n in skill.covered_by
            ):
                continue
            target = entries[entry_no]
            if note not in target.notes:
                target.notes.append(note)
                target.relevance += WEIGHTS[skill.kind]
            if skill.skill not in target.wanted:
                target.wanted.append(skill.skill)

    unmatched = sorted(
        (role for role, entry_no in role_entry.items() if entry_no is None), key=str.lower
    )
    return Matching(posting_skills=posting, entries=entries, unmatched_roles=unmatched)
