"""Rewriting one experience entry, the space budget, and the made-up facts check
(RND-3.4, RND-3.7)."""

import logging
import re
from dataclasses import dataclass, field

from app.core.errors import AppError
from app.core.llm import LLM
from app.core.skills import ALIAS_GROUPS, same_skill, text_mentions_skill
from app.rounder import prompts
from app.rounder.matching import EntrySkills
from app.rounder.schemas import RewrittenEntry

logger = logging.getLogger(__name__)

# How far a reply may go over its budget before trailing bullets are dropped.
BUDGET_SLACK = 1.15
# Space shared by relevance: the most relevant entry gets up to this much more than its share.
RELEVANCE_BOOST = 0.5
MIN_ENTRY_CHARS = 80
MAX_SCALE, MIN_SCALE = 1.25, 0.3

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_WORD = re.compile(r"[A-Za-z][\w+#.&/-]*[\w+#]|[A-Za-z]")
_SENTENCE_END = re.compile(r"[.!?:;]\s*$")
# Technology names from the alias table, written in lower case, that would be easy to slip in.
# Groups that include everyday words ("go", "rest", "react") are left out: they would flag
# ordinary English.
_EVERYDAY = {"golang", "restful api", "next js", "react js", "node js", "elastic search"}
_TECH_WORDS = sorted(
    {sorted(g, key=len, reverse=True)[0] for g in ALIAS_GROUPS} - _EVERYDAY,
    key=str.lower,
)


# --- Space budget ---------------------------------------------------------------------------


def initial_total(bullet_chars: int, template_pages: float, target_pages: float) -> int:
    """Bullet characters for the whole section, scaled from the template to the target."""
    scale = target_pages / template_pages if template_pages > 0 else 1.0
    return round(bullet_chars * min(MAX_SCALE, max(MIN_SCALE, scale)))


def share_budget(original_chars: list[int], relevance: list[int], total: int) -> list[int]:
    """Split `total` across entries, favouring the ones the posting cares about (RND-3.4).

    Growing: every entry keeps its length and the extra goes to relevant entries. Shrinking:
    each entry gets its original share, boosted by relevance, so irrelevant entries lose most.
    """
    if total >= sum(original_chars):
        weights = [c * r for c, r in zip(original_chars, relevance, strict=True)]
        if not any(weights):
            weights = list(original_chars)
        extra, weight_sum = total - sum(original_chars), sum(weights) or 1
        return [
            c + round(extra * w / weight_sum) for c, w in zip(original_chars, weights, strict=True)
        ]
    top = max(relevance, default=0) or 1
    boosted = [
        chars * (1 + RELEVANCE_BOOST * rel / top)
        for chars, rel in zip(original_chars, relevance, strict=True)
    ]
    boosted_sum = sum(boosted) or 1
    return [
        max(min_chars(chars), round(total * w / boosted_sum))
        for chars, w in zip(original_chars, boosted, strict=True)
    ]


def min_chars(original_chars: int) -> int:
    return min(original_chars, MIN_ENTRY_CHARS)


def cut_budgets(
    budgets: list[int], original_chars: list[int], relevance: list[int], amount: int
) -> list[int]:
    """Take `amount` characters away, least relevant entries first, at most half of an entry's
    budget per pass, never going under the minimum."""
    budgets = list(budgets)
    order = sorted(range(len(budgets)), key=lambda i: (relevance[i], -budgets[i]))
    remaining = amount
    while remaining > 0:
        taken_this_pass = 0
        for i in order:
            room = budgets[i] - min_chars(original_chars[i])
            take = min(remaining, room, max(1, budgets[i] // 2))
            if take > 0:
                budgets[i] -= take
                remaining -= take
                taken_this_pass += take
            if remaining <= 0:
                break
        if taken_this_pass == 0:
            break
    return budgets


def fit_to_budget(bullets: list[str], budget: int) -> list[str]:
    """Drop trailing bullets while the total is well over budget, keeping at least one."""
    kept = list(bullets)
    while len(kept) > 1 and sum(len(b) for b in kept) > budget * BUDGET_SLACK:
        kept.pop()
    return kept


# --- Made-up facts check (RND-3.7) ----------------------------------------------------------


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def _words(text: str) -> set[str]:
    return {w.lower().rstrip(".") for w in _WORD.findall(text)}


def _capitalised_terms(bullet: str) -> list[str]:
    """Capitalised words that aren't just starting the bullet or a sentence."""
    terms = []
    for match in _WORD.finditer(bullet):
        word = match.group(0)
        before = bullet[: match.start()]
        if not before.strip() or _SENTENCE_END.search(before):
            continue
        if word[0].isupper() or any(c.isupper() for c in word[1:]):
            terms.append(word.rstrip("."))
    return terms


def made_up_facts(new_bullets: list[str], sources: str) -> list[str]:
    """Numbers, names and known technologies in the new bullets that the sources don't have."""
    source_numbers = _numbers(sources)
    source_words = _words(sources)
    found: list[str] = []

    def add(term: str) -> None:
        if term not in found:
            found.append(term)

    text = "\n".join(new_bullets)
    for number in _NUMBER.findall(text):
        if number.replace(",", "") not in source_numbers:
            add(number)
    for bullet in new_bullets:
        for term in _capitalised_terms(bullet):
            word = term.lower()
            # "API" is fine when the sources say "APIs", and the other way round.
            if not {word, f"{word}s", word.removesuffix("s")} & source_words:
                add(term)
    for variant in _TECH_WORDS:
        if (
            text_mentions_skill(text, variant)
            and not text_mentions_skill(sources, variant)
            and not any(same_skill(variant, term) for term in found)
        ):
            add(variant)
    return found


# --- Rewriting one entry --------------------------------------------------------------------


@dataclass
class EntryResult:
    bullets: list[str]
    skills_used: list[str] = field(default_factory=list)
    kept_original_reason: str | None = None


@dataclass
class EntryJob:
    header: str
    bullets: list[str]
    skills: EntrySkills
    budget: int


def _limits(original: list[str], budget: int) -> tuple[int, int, int]:
    average = max(40, sum(len(b) for b in original) // max(1, len(original)))
    n_max = max(1, round(budget / average))
    n_min = max(1, n_max - 1)
    return n_min, n_max, max(40, budget // n_max)


async def rewrite_entry(llm: LLM, job: EntryJob, job_title: str, company_name: str) -> EntryResult:
    """Rewrite one entry's bullets with its matched skill notes, within its budget.

    If the reply adds facts that aren't in the original bullets or skill notes, ask once more;
    if it still does, keep the original bullets (trimmed to the budget).
    """
    n_min, n_max, per_bullet = _limits(job.bullets, job.budget)
    notes = [(n.skill_name, n.summary) for n in job.skills.notes]
    prompt = prompts.rewrite_entry(
        header=job.header,
        job_title=job_title,
        company_name=company_name,
        wanted=job.skills.wanted,
        bullets=job.bullets,
        notes=notes,
        n_min=n_min,
        n_max=n_max,
        chars_per_bullet=per_bullet,
        char_budget=job.budget,
    )
    sources = "\n".join([job.header, *job.bullets, *(f"{n}: {s}" for n, s in notes)])
    original = fit_to_budget(job.bullets, job.budget)

    facts: list[str] = []
    for attempt in range(2):
        asked = prompt if attempt == 0 else prompts.remove_facts(prompt, facts)
        try:
            reply = await llm.complete_json(asked, RewrittenEntry, system=prompts.REWRITE_SYSTEM)
        except AppError as exc:
            if exc.status_code == 503:  # the LLM is down: the whole generation stops
                raise
            logger.warning("Rewrite of %r failed: %s", job.header, exc.message)
            return EntryResult(original, [], "The local model's reply couldn't be used.")
        bullets = [b.strip().lstrip("-•* ").strip() for b in reply.bullets if b.strip()]
        if not bullets:
            return EntryResult(original, [], "The local model returned no bullets.")
        facts = made_up_facts(bullets, sources)
        if not facts:
            names = {n.lower(): n for n, _ in notes}
            used = [names[s.lower()] for s in reply.skills_used if s.lower() in names]
            return EntryResult(fit_to_budget(bullets, job.budget), list(dict.fromkeys(used)))
    return EntryResult(
        original,
        [],
        "The rewrite added details that aren't in your resume or skill notes "
        f"({', '.join(facts[:5])}), so the original bullets were kept.",
    )
