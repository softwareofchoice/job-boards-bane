"""The resume generation pipeline, steps 3 to 8 of the design (RND-3).

It works on bytes and plain values and knows nothing of the database, so the background job and
`make rounder-eval` share it.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.errors import AppError
from app.core.llm import LLM
from app.rounder import matching, resume_doc
from app.rounder.matching import EntrySkills, SkillNote
from app.rounder.pages import PageMeasurer, Rendered
from app.rounder.resume_doc import ResumeModel
from app.rounder.rewrite import (
    EntryJob,
    EntryResult,
    cut_budgets,
    initial_total,
    rewrite_entry,
    share_budget,
)
from app.rounder.schemas import (
    EntryReport,
    PagesReport,
    PostingSkillReport,
    Report,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3  # renders, counting the first: up to two rounds of shortening (RND-3.9)
SHORTEN_STEP = 0.15
UNDER_TARGET_WARNING = 0.5  # pages (RND-3.8)
# An entry with no matched skills keeps its bullets unless its budget is this much smaller.
KEEP_ORIGINAL_RATIO = 0.95

Progress = Callable[..., None]


class DocumentChangedError(AppError):
    """The writer touched something outside the experience bullets. Always a bug (RND-3.5)."""

    status_code = 500
    code = "document_changed"


@dataclass
class GenerationInput:
    template: bytes
    posting_text: str
    job_title: str
    company_name: str
    target_pages: float
    heading_idx: int | None
    skills: list[SkillNote]


@dataclass
class GenerationResult:
    docx: bytes
    pdf: bytes
    report: Report
    page_count: int
    pages: float
    heading_idx: int


@dataclass
class _Attempt:
    docx: bytes
    rendered: Rendered
    results: dict[int, EntryResult]


def _no_progress(**_: Any) -> None:
    pass


async def generate(
    inp: GenerationInput,
    llm: LLM,
    measurer: PageMeasurer,
    progress: Progress = _no_progress,
) -> GenerationResult:
    model = resume_doc.read_resume(inp.template, inp.heading_idx)
    template_render = await asyncio.to_thread(measurer.render, inp.template)
    template_pages = template_render.pages or 1.0

    # 3-4. Posting skills, matched to saved skills and experience entries.
    progress(step="finding_skills")
    posting = await matching.extract_posting_skills(llm, inp.posting_text)
    await matching.match_skills(llm, posting, [s.skill_name for s in inp.skills])
    headers = [e.header_text for e in model.entries]
    matched = matching.assign(posting, inp.skills, headers)

    # 5. Space budget, then rewrite.
    entries = [i for i, e in enumerate(model.entries) if e.bullets]
    original = [model.entries[i].chars for i in entries]
    relevance = [matched.entries.get(i, EntrySkills()).relevance for i in entries]
    total = initial_total(sum(original), template_pages, inp.target_pages)
    budgets = share_budget(original, relevance, total)

    results: dict[int, EntryResult] = {}

    async def rewrite(changed: list[int]) -> None:
        for done, k in enumerate(changed):
            progress(step="rewriting", done=done, total=len(changed))
            i = entries[k]
            entry = model.entries[i]
            skills = matched.entries.get(i, EntrySkills())
            if not skills.notes and budgets[k] >= original[k] * KEEP_ORIGINAL_RATIO:
                results[i] = EntryResult(
                    list(entry.bullets), [], "No saved skills matched this role."
                )
                continue
            job = EntryJob(entry.header_text, entry.bullets, skills, budgets[k])
            results[i] = await rewrite_entry(llm, job, inp.job_title, inp.company_name)
        progress(step="rewriting", done=len(changed), total=len(changed))

    await rewrite(list(range(len(entries))))

    # 6. Check the length; shorten and retry while it's over the target.
    chars_per_page = model.total_chars / template_pages
    attempts: list[_Attempt] = []
    while True:
        progress(step="checking_length", attempt=len(attempts) + 1, max_attempts=MAX_ATTEMPTS)
        docx = _write(inp.template, model, results)
        rendered = await asyncio.to_thread(measurer.render, docx)
        attempts.append(_Attempt(docx, rendered, dict(results)))
        overflow = rendered.pages - inp.target_pages
        if overflow <= 0 or len(attempts) >= MAX_ATTEMPTS:
            break
        cut = max(round(sum(budgets) * SHORTEN_STEP), round(overflow * chars_per_page))
        new_budgets = cut_budgets(budgets, original, relevance, cut)
        changed = [k for k in range(len(entries)) if new_budgets[k] != budgets[k]]
        if not changed:
            break
        budgets = new_budgets
        await rewrite(changed)

    best = min(attempts, key=lambda a: a.rendered.pages)
    # 8. Nothing outside the experience bullets may differ from the template.
    if diff := resume_doc.changes_outside_bullets(inp.template, best.docx, model.heading_idx):
        raise DocumentChangedError(
            f"Internal error: the generated resume changed parts it must not touch ({diff[0]})."
        )
    report = _report(model, matched, best, template_pages, inp.target_pages, len(attempts))
    progress(step="done")
    return GenerationResult(
        docx=best.docx,
        pdf=best.rendered.pdf,
        report=report,
        page_count=best.rendered.page_count,
        pages=best.rendered.pages,
        heading_idx=model.heading_idx,
    )


def _write(template: bytes, model: ResumeModel, results: dict[int, EntryResult]) -> bytes:
    new = {i: r.bullets for i, r in results.items() if r.bullets != model.entries[i].bullets}
    return resume_doc.write_resume(template, model, new)


def _report(
    model: ResumeModel,
    matched: matching.Matching,
    best: _Attempt,
    template_pages: float,
    target: float,
    attempts: int,
) -> Report:
    pages = best.rendered.pages
    overflow = round(pages - target, 2) if pages > target else None
    warnings = list(model.warnings)
    if overflow is not None:
        warnings.append(
            f"Couldn't fit the resume in {target:g} pages after {attempts} attempts: the "
            f"closest is {overflow:g} pages over."
        )
    elif target - pages > UNDER_TARGET_WARNING:
        warnings.append(
            f"The resume is {target - pages:.1f} pages shorter than the {target:g}-page target."
        )
    if not any(s.covered_by for s in matched.posting_skills):
        warnings.append("None of your saved skills matched the skills this posting asks for.")

    entries = []
    for i, entry in enumerate(model.entries):
        if not entry.bullets:
            continue
        result = best.results.get(i, EntryResult(entry.bullets))
        skills = matched.entries.get(i, EntrySkills())
        entries.append(
            EntryReport(
                header=entry.header_text,
                role=skills.role,
                before=entry.bullets,
                after=result.bullets,
                skills_used=result.skills_used,
                kept_original_reason=result.kept_original_reason,
            )
        )
    return Report(
        posting_skills=[
            PostingSkillReport(
                skill=s.skill,
                kind=s.kind,
                covered_by=", ".join(s.covered_by) if s.covered_by else None,
            )
            for s in matched.posting_skills
        ],
        unmatched_roles=matched.unmatched_roles,
        entries=entries,
        pages=PagesReport(
            target=target,
            template=round(template_pages, 2),
            final=pages,
            attempts=attempts,
            overflow=overflow,
        ),
        warnings=warnings,
    )
