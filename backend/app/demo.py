"""Canned LLM replies for LLM_FAKE=true: lets the whole app run (and E2E tests pass) without
Ollama. Replies are derived from the prompt so results look plausible and are repeatable."""

import json
import re

from app.core.llm_fake import FakeLLMClient
from app.core.skills import ALIAS_GROUPS, text_mentions_skill


def _field(prompt: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:?\s*(.*)$", prompt, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", text.lower()))


def score_reply(prompt: str) -> str:
    """A ScoreResponse for the scraper's scoring prompt."""
    wanted = _words(_field(prompt, "- Desired title"))
    title = _words(_field(prompt, "Title"))
    title_fit = round(10 * len(wanted & title) / len(wanted)) if wanted else 5
    location_wanted = _field(prompt, "- Location").lower()
    location = _field(prompt, "Location").lower()
    location_fit = 10 if location_wanted in ("any", "") or location_wanted in location else 4
    return json.dumps(
        {
            "title_fit": title_fit,
            "skills": 5,
            "experience": 7,
            "level": 6,
            "location": location_fit,
            "matched_skills": [],
            "missing_skills": [],
            "rationale": f"Demo score: the title overlaps {len(wanted & title)} word(s).",
        }
    )


# Words that look like technology names: acronyms (SQL, AWS) and mixed case (FastAPI, GitHub).
_TECH = re.compile(r"\b(?:[A-Z]{2,}[a-z]*|[A-Z][a-z]+[A-Z][A-Za-z]*)\b")


def _section(prompt: str, label: str) -> str:
    """The lines after `LABEL:` up to the next blank line."""
    match = re.search(rf"^{re.escape(label)}:\n(.*?)(?:\n\n|\Z)", prompt, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def posting_skills_reply(prompt: str) -> str:
    """Rounder: skills named in the posting, from the alias table and tech-looking words,
    spelled as the posting spells them."""
    posting = prompt.split("POSTING:\n", 1)[-1]
    found: list[str] = []

    def add(name: str) -> None:
        if not any(text_mentions_skill(f, name) or text_mentions_skill(name, f) for f in found):
            found.append(name)

    for group in ALIAS_GROUPS:
        for variant in sorted(group, key=len, reverse=True):
            pattern = rf"(?<![\w+#]){re.escape(variant)}(?![\w+#])"
            if len(variant) > 2 and (match := re.search(pattern, posting, re.IGNORECASE)):
                add(match.group(0))
                break
    for word in _TECH.findall(posting):
        add(word)
    return json.dumps({"required": found[:8], "preferred": found[8:12]})


def rewrite_reply(prompt: str) -> str:
    """Rounder: the skill notes as new bullets, then the original bullets, within the limit."""
    notes = [line[2:] for line in _section(prompt, "SKILL NOTES (from the candidate)").splitlines()]
    notes = [n for n in notes if n and n != "(none)"]
    originals = [line[2:] for line in _section(prompt, "ORIGINAL BULLETS").splitlines()]
    limit = re.search(r"Write \d+-(\d+) bullets", prompt)
    n_max = int(limit.group(1)) if limit else 3
    names = [n.split(":", 1)[0] for n in notes]
    from_notes = [n.split(":", 1)[1].strip() for n in notes if ":" in n]
    bullets = (from_notes + originals)[:n_max]
    return json.dumps({"bullets": bullets, "skills_used": names})


def reply(prompt: str) -> str:
    if "JOB POSTING" in prompt and "CANDIDATE SEARCH" in prompt:
        return score_reply(prompt)
    if "POSTING SKILLS:" in prompt and "SAVED SKILLS:" in prompt:
        return json.dumps({"pairs": []})
    if prompt.startswith("List the skills") and "POSTING:" in prompt:
        return posting_skills_reply(prompt)
    if "ORIGINAL BULLETS:" in prompt:
        return rewrite_reply(prompt)
    return "{}"


def demo_llm() -> FakeLLMClient:
    client = FakeLLMClient(default=reply)
    client.model = "demo (LLM_FAKE)"
    return client
