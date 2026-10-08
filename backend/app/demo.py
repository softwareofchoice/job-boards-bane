"""Canned LLM replies for LLM_FAKE=true: lets the whole app run (and E2E tests pass) without
Ollama. Replies are derived from the prompt so results look plausible and are repeatable."""

import json
import re

from app.core.llm_fake import FakeLLMClient


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


def reply(prompt: str) -> str:
    if "JOB POSTING" in prompt and "CANDIDATE SEARCH" in prompt:
        return score_reply(prompt)
    return "{}"


def demo_llm() -> FakeLLMClient:
    client = FakeLLMClient(default=reply)
    client.model = "demo (LLM_FAKE)"
    return client
