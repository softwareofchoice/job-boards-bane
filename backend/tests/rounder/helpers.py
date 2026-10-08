import json
import math
from typing import Any

from app.rounder import resume_doc
from app.rounder.matching import SkillNote
from app.rounder.pages import Rendered

FAKE_PDF = b"%PDF-1.7\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"

POSTING = (
    "Initech is hiring a Backend Engineer to build the services behind our billing platform. "
    "Required: Python, PostgreSQL and Kubernetes, plus experience designing REST APIs. "
    "Preferred: FastAPI and Terraform. You'll work with product and support teams to ship "
    "reliable features every week and mentor other engineers."
)

NORTHWIND = "Senior Software Engineer at Northwind Analytics"
FABRIKAM = "Software Engineer at Fabrikam Logistics"

NOTES = [
    SkillNote(
        "Postgres",
        NORTHWIND,
        "Designed the Postgres schema for the analytics store and tuned indexes.",
    ),
    SkillNote("FastAPI", NORTHWIND, "Built internal FastAPI services for report generation."),
    SkillNote("Kubernetes", FABRIKAM, "Deployed the tracking service to Kubernetes with Helm."),
    SkillNote("Rust", "Open source maintainer", "Wrote a command-line tool in Rust."),
]


class EstimateMeasurer:
    """Stands in for LibreOffice: a page is `chars_per_page` characters of text."""

    def __init__(self, chars_per_page: int = 1500) -> None:
        self.chars_per_page = chars_per_page
        self.rendered: list[float] = []

    def render(self, docx: bytes) -> Rendered:
        doc = resume_doc.load(docx)
        chars = sum(len(p.text) for p in resume_doc.paragraphs(doc))
        pages = round(chars / self.chars_per_page, 2)
        self.rendered.append(pages)
        return Rendered(pdf=FAKE_PDF, page_count=max(1, math.ceil(pages)), pages=pages)


def posting_skills(required: list[str], preferred: list[str] | None = None) -> str:
    return json.dumps({"required": required, "preferred": preferred or []})


def pairs(*items: tuple[str, str]) -> str:
    return json.dumps({"pairs": [{"posting_skill": a, "saved_skill": b} for a, b in items]})


def rewritten(bullets: list[str], skills_used: list[str] | None = None) -> str:
    return json.dumps({"bullets": bullets, "skills_used": skills_used or []})


def section(prompt: str, label: str) -> list[str]:
    """The `- ` lines under `LABEL:` in a rewrite prompt."""
    block = prompt.split(f"{label}:\n", 1)[1].split("\n\n", 1)[0]
    return [line[2:] for line in block.splitlines()]


def echo_rewrite(prompt: str) -> str:
    """A rewrite reply that uses the skill notes and the original bullets, inventing nothing."""
    notes = [
        n.split(": ", 1)[1]
        for n in section(prompt, "SKILL NOTES (from the candidate)")
        if ": " in n
    ]
    names = [
        n.split(": ", 1)[0]
        for n in section(prompt, "SKILL NOTES (from the candidate)")
        if ": " in n
    ]
    n_max = int(prompt.split("Write ", 1)[1].split(" bullets", 1)[0].split("-")[1])
    return rewritten((notes + section(prompt, "ORIGINAL BULLETS"))[:n_max], names)


def router(**replies: Any) -> Any:
    """A fake LLM reply function that answers each kind of rounder prompt."""

    def reply(prompt: str) -> str:
        if prompt.startswith("List the skills"):
            return str(replies.get("extract", posting_skills(["PostgreSQL", "Kubernetes"])))
        if "POSTING SKILLS:" in prompt:
            return str(replies.get("pairs", pairs()))
        if "ORIGINAL BULLETS:" in prompt:
            rewrite = replies.get("rewrite", echo_rewrite)
            return str(rewrite(prompt) if callable(rewrite) else rewrite)
        raise AssertionError(f"Unexpected prompt: {prompt[:80]}")

    return reply
