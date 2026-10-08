"""`make rounder-eval`: a quality check of the Resume Rounder against the real local model.

Runs three sample postings against two sample resumes with a sample skills library, and writes
each result (`.docx`, `.pdf`, `report.json` and a readable `report.md`) to `data/eval/<time>/`.
A person reads them to judge whether the rewrites are good and invent nothing (RND-3.4, RND-3.7).
Not run in CI: it needs Ollama, LibreOffice and several minutes.

    uv run python -m app.rounder_eval [--model NAME] [--target PAGES]
"""

import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.core.errors import AppError
from app.core.llm import LLMClient
from app.rounder import sample_resumes
from app.rounder.generate import GenerationInput, GenerationResult, generate
from app.rounder.matching import SkillNote
from app.rounder.pages import LibreOfficeMeasurer

NORTHWIND = "Senior Software Engineer at Northwind Analytics"
FABRIKAM = "Software Engineer at Fabrikam Logistics"
CONTOSO = "Junior Developer at Contoso Retail"

SKILLS = [
    SkillNote(
        "PostgreSQL",
        NORTHWIND,
        "Designed the reporting schema and added indexes that made the slowest dashboard "
        "queries ten times faster.",
    ),
    SkillNote("FastAPI", NORTHWIND, "Built three internal FastAPI services for report exports."),
    SkillNote("Redis", NORTHWIND, "Added a Redis cache in front of the most-used queries."),
    SkillNote("Kubernetes", FABRIKAM, "Moved the tracking service onto Kubernetes with Helm."),
    SkillNote("Django", FABRIKAM, "Built the shipment tracking pages and admin tools in Django."),
    SkillNote("CI/CD", FABRIKAM, "Set up GitHub Actions to test and deploy on every merge."),
    SkillNote("JavaScript", CONTOSO, "Rewrote the checkout form validation in JavaScript."),
    SkillNote("Accessibility", CONTOSO, "Fixed keyboard navigation on the checkout pages."),
]

POSTINGS = {
    "backend-engineer": (
        "Backend Engineer",
        "Initech",
        "Initech is hiring a Backend Engineer to build the services behind our billing "
        "platform. Required: Python, PostgreSQL, REST API design and Kubernetes. Preferred: "
        "FastAPI, Redis and experience with CI/CD pipelines. You'll work closely with product "
        "and support teams, review code, and help us keep the platform fast and reliable as "
        "we grow.",
    ),
    "full-stack-developer": (
        "Full Stack Developer",
        "Globex",
        "Globex is looking for a Full Stack Developer. You'll build features end to end in "
        "Django and JavaScript, care about accessibility, and write automated tests. Required: "
        "Python, Django, JavaScript, SQL. Nice to have: React, Docker, and experience mentoring "
        "junior developers. Our team ships small changes many times a day.",
    ),
    "data-platform-engineer": (
        "Data Platform Engineer",
        "Umbrella Analytics",
        "Umbrella Analytics needs a Data Platform Engineer to own our reporting pipelines. "
        "Required: Python, Postgres, query performance tuning, and queue-based job systems. "
        "Preferred: Kubernetes, Terraform and AWS. You will partner with analysts to define "
        "data models and make dashboards fast.",
    ),
}

RESUMES = {"styled": sample_resumes.styled, "caps": sample_resumes.caps}


def markdown(name: str, result: GenerationResult, seconds: float) -> str:
    report = result.report
    lines = [f"# {name}", "", f"Pages: {report.pages.model_dump()} · {seconds:.0f} s", ""]
    lines += ["## Posting skills", ""]
    lines += [
        f"- {s.skill} ({s.kind}): {s.covered_by or '**not covered**'}"
        for s in report.posting_skills
    ]
    if report.unmatched_roles:
        lines += ["", f"Unmatched roles: {', '.join(report.unmatched_roles)}"]
    for entry in report.entries:
        lines += ["", f"## {entry.header}", "", f"Skills used: {', '.join(entry.skills_used)}"]
        if entry.kept_original_reason:
            lines += [f"Kept original: {entry.kept_original_reason}"]
        lines += ["", "Before:", *[f"- {b}" for b in entry.before]]
        lines += ["", "After:", *[f"- {b}" for b in entry.after]]
    if report.warnings:
        lines += ["", "## Warnings", "", *[f"- {w}" for w in report.warnings]]
    return "\n".join(lines) + "\n"


async def run(model: str | None, target: float) -> int:
    settings = get_settings()
    llm = LLMClient(
        settings.llm_base_url,
        model or settings.llm_model,
        timeout_s=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        num_ctx=settings.llm_num_ctx,
    )
    measurer = LibreOfficeMeasurer(settings.soffice_path, settings.soffice_timeout_s)
    try:
        await llm.check()
    except AppError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    out = settings.data_dir / "eval" / datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"Model {llm.model}; writing results to {out}")
    for posting_name, (title, company, text) in POSTINGS.items():
        for resume_name, build in RESUMES.items():
            name = f"{posting_name}--{resume_name}"
            started = time.monotonic()
            inp = GenerationInput(build(), text, title, company, target, None, SKILLS)
            try:
                result = await generate(inp, llm, measurer)
            except AppError as exc:
                print(f"  {name}: FAILED: {exc.message}")
                continue
            seconds = time.monotonic() - started
            folder = Path(out, name)
            folder.mkdir(parents=True)
            (folder / "resume.docx").write_bytes(result.docx)
            (folder / "resume.pdf").write_bytes(result.pdf)
            (folder / "report.json").write_text(result.report.model_dump_json(indent=2))
            (folder / "report.md").write_text(markdown(name, result, seconds))
            print(f"  {name}: {result.pages} pages in {seconds:.0f} s")
    print(f"Read the reports in {out} (report.md in each folder).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", help="Ollama model to use instead of LLM_MODEL")
    parser.add_argument("--target", type=float, default=1.0, help="target pages (default 1)")
    args = parser.parse_args()
    return asyncio.run(run(args.model, args.target))


if __name__ == "__main__":
    raise SystemExit(main())
