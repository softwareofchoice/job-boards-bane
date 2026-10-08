"""Scores a posting against the search with the local LLM (SCR-4.1 to SCR-4.3, SCR-4.7)."""

from dataclasses import dataclass

from app.config import Settings
from app.core.llm import LLM
from app.core.skills import canonical_skill, text_mentions_skill
from app.scraper.schemas import RawPosting, ScoreResponse, SearchOptions, SubScores

SYSTEM_PROMPT = (
    "You are a recruiting assistant. Rate how well a job posting matches a candidate's search. "
    "Be strict and consistent. Reply only with JSON matching the schema."
)

PROMPT_TEMPLATE = """CANDIDATE SEARCH
- Desired title: {job_title}
- Location: {location}
- Years of experience: {years_experience}
- Desired level: {job_level}
- Skills: {skills}

JOB POSTING
Title: {title}
Company: {company}
Location: {posting_location}
Description (truncated to {max_chars} chars):
{description}

Score each criterion 0-10: title_fit, skills, experience, level, location.
List matched_skills and missing_skills (from the candidate's skills only).
Give a rationale of at most 2 sentences."""


@dataclass(frozen=True)
class Weights:
    title_fit: float = 30
    skills: float = 30
    experience: float = 15
    level: float = 15
    location: float = 10

    @classmethod
    def from_settings(cls, settings: Settings) -> "Weights":
        return cls(
            title_fit=settings.score_weight_title,
            skills=settings.score_weight_skills,
            experience=settings.score_weight_experience,
            level=settings.score_weight_level,
            location=settings.score_weight_location,
        )


@dataclass(frozen=True)
class Score:
    overall: int
    sub_scores: SubScores
    matched_skills: list[str]
    missing_skills: list[str]
    rationale: str


def build_prompt(opts: SearchOptions, posting: RawPosting, max_chars: int) -> str:
    return PROMPT_TEMPLATE.format(
        job_title=opts.job_title,
        location=opts.location or "any",
        years_experience=opts.years_experience,
        job_level=opts.job_level.label,
        skills=", ".join(opts.skills),
        title=posting.title,
        company=posting.company,
        posting_location=posting.location or "not stated",
        max_chars=max_chars,
        description=posting.description[:max_chars],
    )


def match_skills(
    opts: SearchOptions, posting: RawPosting, llm_matched: list[str]
) -> tuple[list[str], list[str]]:
    """The user's skills the posting mentions, and the rest (SCR-4.7).

    Found by text search with aliases, so more matching skills always means more matches
    (SCR-4.3). The LLM's list only adds synonyms the alias table missed, and only skills the
    user actually listed.
    """
    text = f"{posting.title}\n{posting.description}"
    llm_canon = {canonical_skill(s) for s in llm_matched}
    matched = [
        s for s in opts.skills if text_mentions_skill(text, s) or canonical_skill(s) in llm_canon
    ]
    missing = [s for s in opts.skills if s not in matched]
    return matched, missing


def overall_score(sub: SubScores, weights: Weights) -> int:
    pairs = [
        (sub.title_fit, weights.title_fit),
        (sub.skills, weights.skills),
        (sub.experience, weights.experience),
        (sub.level, weights.level),
        (sub.location, weights.location),
    ]
    total_weight = sum(w for _, w in pairs)
    if total_weight <= 0:
        pairs = [(s, 1.0) for s, _ in pairs]
        total_weight = len(pairs)
    return round(sum(s * w for s, w in pairs) / total_weight * 10)


async def score_posting(
    llm: LLM, opts: SearchOptions, posting: RawPosting, *, weights: Weights, max_chars: int
) -> Score:
    reply = await llm.complete_json(
        build_prompt(opts, posting, max_chars), ScoreResponse, system=SYSTEM_PROMPT
    )
    matched, missing = match_skills(opts, posting, reply.matched_skills)
    sub = SubScores(
        title_fit=reply.title_fit,
        skills=round(10 * len(matched) / len(opts.skills)),
        experience=reply.experience,
        level=reply.level,
        location=reply.location,
    )
    return Score(
        overall=overall_score(sub, weights),
        sub_scores=sub,
        matched_skills=matched,
        missing_skills=missing,
        rationale=reply.rationale.strip(),
    )
