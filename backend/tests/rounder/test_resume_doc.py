import io

import pytest
from docx.oxml.ns import qn

from app.rounder import sample_resumes
from app.rounder.resume_doc import (
    ExperienceSectionNotFoundError,
    InvalidTemplateError,
    changes_outside_bullets,
    load,
    paragraphs,
    read_resume,
    set_paragraph_text,
    write_resume,
)
from tests.samples import docx as broken_docx

FIRST_BULLETS = [b for _, _, b in sample_resumes.ENTRIES]


@pytest.mark.parametrize("name", ["styled-1-page", "caps-headings", "table-layout"])
def test_each_layout_gives_the_entries_and_their_bullets(name: str) -> None:
    model = read_resume(sample_resumes.SAMPLES[name]())
    assert [e.bullets for e in model.entries] == FIRST_BULLETS
    for entry, (role, dates, _) in zip(model.entries, sample_resumes.ENTRIES, strict=True):
        assert role in entry.header_text and dates in entry.header_text


def test_the_section_ends_at_the_next_heading_of_the_same_level() -> None:
    model = read_resume(sample_resumes.styled(long=True))
    # The Projects section's bullets come after experience and aren't part of it.
    assert len(model.entries) == len(sample_resumes.ENTRIES + sample_resumes.EXTRA_ENTRIES)
    texts = [p.text for p in paragraphs(load(sample_resumes.styled(long=True)))]
    assert texts[model.heading_idx] == "Experience"
    assert texts[model.end_idx] == "Projects"


def test_a_table_layout_is_read_with_a_warning() -> None:
    model = read_resume(sample_resumes.table())
    assert any("table" in w for w in model.warnings)


def test_no_experience_section_lists_the_headings_to_choose_from() -> None:
    with pytest.raises(ExperienceSectionNotFoundError) as caught:
        read_resume(sample_resumes.no_experience())
    texts = [h.text for h in caught.value.headings]
    assert texts == ["Alex Rivera", "Summary", "Projects", "Education"]
    assert caught.value.details["headings"][2]["text"] == "Projects"


def test_a_chosen_heading_overrides_the_search() -> None:
    data = sample_resumes.no_experience()
    with pytest.raises(ExperienceSectionNotFoundError) as caught:
        read_resume(data)
    projects = next(h for h in caught.value.headings if h.text == "Projects")
    model = read_resume(data, projects.index)
    assert [len(e.bullets) for e in model.entries] == [7]


def test_a_chosen_index_that_is_not_a_paragraph_is_rejected() -> None:
    with pytest.raises(ExperienceSectionNotFoundError):
        read_resume(sample_resumes.styled(), 9999)


def test_a_file_that_is_not_a_word_document_is_rejected() -> None:
    with pytest.raises(InvalidTemplateError):
        read_resume(broken_docx())
    with pytest.raises(InvalidTemplateError):
        read_resume(b"not a zip")


@pytest.mark.parametrize(
    "name", ["styled-1-page", "styled-2-pages", "caps-headings", "table-layout"]
)
def test_replace_add_and_remove_bullets_touch_nothing_else(name: str) -> None:
    template = sample_resumes.SAMPLES[name]()
    model = read_resume(template)
    new = {0: ["One.", "Two.", "Three.", "Four.", "Five.", "Six."], 1: ["Only."]}
    output = write_resume(template, model, new)

    after = read_resume(output, model.heading_idx)
    assert after.entries[0].bullets == new[0]
    assert after.entries[1].bullets == new[1]
    assert after.entries[2].bullets == model.entries[2].bullets
    assert [e.header_text for e in after.entries] == [e.header_text for e in model.entries]
    assert changes_outside_bullets(template, output, model.heading_idx) == []


def _bullet_formatting(data: bytes, idx: int) -> tuple[bytes, bytes | None]:
    p = paragraphs(load(data))[idx]._p
    ppr = p.find(qn("w:pPr"))
    run = p.find(qn("w:r"))
    rpr = run.find(qn("w:rPr")) if run is not None else None
    return (ppr.xml.encode(), rpr.xml.encode() if rpr is not None else None)


def test_rewritten_and_added_bullets_keep_the_paragraph_and_run_formatting() -> None:
    template = sample_resumes.caps()
    model = read_resume(template)
    first = model.entries[0].bullet_idxs[0]
    last = model.entries[0].bullet_idxs[-1]
    original = _bullet_formatting(template, first)

    texts = [f"Bullet {n}." for n in range(6)]
    output = write_resume(template, model, {0: texts})
    for k in range(6):  # replaced ones keep theirs; added ones copy the last bullet's
        assert _bullet_formatting(output, first + k) == original
    out_paras = paragraphs(load(output))
    # The typed bullet character and its tab are kept.
    assert out_paras[first].text == "•\tBullet 0."
    assert out_paras[last + 2].text == "•\tBullet 5."


def test_set_text_keeps_the_first_runs_font() -> None:
    doc = load(sample_resumes.styled())
    p = paragraphs(doc)[0]  # the name: bold, 18pt
    set_paragraph_text(p._p, "Someone Else")
    run = p.runs[0]
    assert len(p.runs) == 1 and run.text == "Someone Else"
    assert run.bold is True and run.font.size is not None and run.font.size.pt == 18


def test_the_check_catches_a_changed_paragraph_outside_the_bullets() -> None:
    template = sample_resumes.styled()
    model = read_resume(template)
    output = write_resume(template, model, {0: ["Changed."]})
    doc = load(output)
    header = paragraphs(doc)[model.entries[0].header_idxs[0]]
    header.runs[0].text = "Chief Everything Officer, Northwind Analytics"
    buf = io.BytesIO()
    doc.save(buf)
    assert changes_outside_bullets(template, buf.getvalue(), model.heading_idx) == ["document body"]


def test_the_check_catches_a_change_in_another_part() -> None:
    template = sample_resumes.styled()
    model = read_resume(template)
    doc = load(template)
    doc.sections[0].header.paragraphs[0].text = "Confidential"
    buf = io.BytesIO()
    doc.save(buf)
    changed = changes_outside_bullets(template, buf.getvalue(), model.heading_idx)
    # Adding a page header creates a new part (and its relationship from the document).
    assert any("header" in name for name in changed)
