import os
import shutil
from typing import Any

import pytest

from app.core.llm_fake import FakeLLMClient
from app.rounder import resume_doc, sample_resumes
from app.rounder.generate import MAX_ATTEMPTS, GenerationInput, generate
from app.rounder.pages import LibreOfficeMeasurer
from app.rounder.resume_doc import ExperienceSectionNotFoundError
from tests.rounder.helpers import NOTES, POSTING, EstimateMeasurer, rewritten, router


def inp(template: bytes, target: float = 1.0, **overrides: Any) -> GenerationInput:
    data: dict[str, Any] = {
        "template": template,
        "posting_text": POSTING,
        "job_title": "Backend Engineer",
        "company_name": "Initech",
        "target_pages": target,
        "heading_idx": None,
        "skills": NOTES,
    }
    data.update(overrides)
    return GenerationInput(**data)


@pytest.mark.parametrize("name", ["styled-1-page", "caps-headings", "table-layout"])
async def test_the_pipeline_fits_the_target_and_reports(name: str) -> None:
    template = sample_resumes.SAMPLES[name]()
    steps: list[dict[str, Any]] = []
    llm = FakeLLMClient(default=router())
    result = await generate(inp(template), llm, EstimateMeasurer(), lambda **p: steps.append(p))

    report = result.report
    assert result.pages <= 1.0
    assert report.pages.attempts == 1 and report.pages.overflow is None
    coverage = {s.skill: s.covered_by for s in report.posting_skills}
    assert coverage == {"PostgreSQL": "Postgres", "Kubernetes": "Kubernetes"}
    assert report.unmatched_roles == ["Open source maintainer"]
    northwind, fabrikam, contoso = report.entries
    assert northwind.skills_used == ["Postgres"]
    assert northwind.after[0].startswith("Designed the Postgres schema")
    assert fabrikam.after[0].startswith("Deployed the tracking service to Kubernetes")
    assert contoso.after == contoso.before
    assert contoso.kept_original_reason == "No saved skills matched this role."
    assert steps[0]["step"] == "finding_skills"
    assert {"rewriting", "checking_length", "done"} <= {s["step"] for s in steps}
    # The output is the template with only the bullets changed.
    model = resume_doc.read_resume(result.docx, result.heading_idx)
    assert [e.bullets for e in model.entries] == [e.after for e in report.entries]
    assert resume_doc.changes_outside_bullets(template, result.docx, result.heading_idx) == []


async def test_text_that_never_fits_is_returned_with_the_overflow() -> None:
    template = sample_resumes.styled()
    long_bullets = [f"Designed the Postgres schema and tuned indexes {'x' * 400}"] * 6
    llm = FakeLLMClient(default=router(rewrite=rewritten(long_bullets)))
    measurer = EstimateMeasurer(chars_per_page=900)
    result = await generate(inp(template), llm, measurer, lambda **_: None)

    assert result.report.pages.attempts == MAX_ATTEMPTS
    assert result.report.pages.overflow is not None and result.report.pages.overflow > 0
    assert result.pages == min(measurer.rendered[1:])  # the closest attempt
    assert any("Couldn't fit" in w for w in result.report.warnings)


async def test_shortening_rewrites_with_smaller_budgets_until_it_fits() -> None:
    template = sample_resumes.styled(long=True)
    llm = FakeLLMClient(default=router())
    measurer = EstimateMeasurer(chars_per_page=2000)
    template_pages = measurer.render(template).pages
    result = await generate(inp(template, target=1.0), llm, measurer, lambda **_: None)
    assert template_pages > 1.0
    assert result.pages <= 1.0
    budgets = [int(p.split("at most ")[1].split(" ")[0]) for p in llm.prompts if "at most" in p]
    assert budgets  # rewrites were asked to fit a budget


async def test_a_made_up_employer_keeps_that_entrys_original_bullets() -> None:
    template = sample_resumes.styled()
    llm = FakeLLMClient(
        default=router(rewrite=rewritten(["Led migrations at Globex Corporation."]))
    )
    result = await generate(inp(template), llm, EstimateMeasurer(), lambda **_: None)
    northwind = result.report.entries[0]
    assert northwind.after == northwind.before
    assert northwind.kept_original_reason and "Globex" in northwind.kept_original_reason


async def test_much_shorter_than_the_target_is_a_warning() -> None:
    template = sample_resumes.styled()
    llm = FakeLLMClient(default=router())
    result = await generate(inp(template, target=3.0), llm, EstimateMeasurer(), lambda **_: None)
    assert any("shorter than the 3-page target" in w for w in result.report.warnings)


async def test_no_matched_skills_is_a_warning() -> None:
    llm = FakeLLMClient(default=router(extract='{"required": ["COBOL"], "preferred": []}'))
    result = await generate(inp(sample_resumes.styled()), llm, EstimateMeasurer(), lambda **_: None)
    assert any("None of your saved skills" in w for w in result.report.warnings)


async def test_a_missing_experience_section_stops_before_any_llm_work() -> None:
    llm = FakeLLMClient()
    with pytest.raises(ExperienceSectionNotFoundError):
        await generate(inp(sample_resumes.no_experience()), llm, EstimateMeasurer())
    assert llm.prompts == []


def soffice_available() -> bool:
    if shutil.which("soffice"):
        return True
    if os.environ.get("REQUIRE_SOFFICE") == "1":
        pytest.fail("REQUIRE_SOFFICE=1 but LibreOffice (soffice) isn't installed")
    return False


@pytest.mark.skipif(not soffice_available(), reason="LibreOffice (soffice) isn't installed")
async def test_with_libreoffice_the_two_page_resume_is_fitted_to_two_pages() -> None:
    template = sample_resumes.styled(long=True)
    measurer = LibreOfficeMeasurer()
    llm = FakeLLMClient(default=router())
    result = await generate(inp(template, target=2.0), llm, measurer, lambda **_: None)
    assert result.pdf.startswith(b"%PDF")
    assert result.page_count == 2 and result.pages <= 2.0
    assert resume_doc.changes_outside_bullets(template, result.docx, result.heading_idx) == []
