import io
import os
import shutil

import pytest
from docx import Document

from app.rounder import sample_resumes
from app.rounder.pages import LibreOfficeMeasurer, LibreOfficeMissingError, bottom_margin_pt


def soffice_available() -> bool:
    if shutil.which("soffice"):
        return True
    if os.environ.get("REQUIRE_SOFFICE") == "1":
        pytest.fail("REQUIRE_SOFFICE=1 but LibreOffice (soffice) isn't installed")
    return False


needs_soffice = pytest.mark.skipif(
    not soffice_available(), reason="LibreOffice (soffice) isn't installed"
)


def with_footer(data: bytes) -> bytes:
    doc = Document(io.BytesIO(data))
    doc.sections[0].footer.paragraphs[0].text = "Alex Rivera · page 1"
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def test_a_missing_soffice_is_a_clear_error() -> None:
    with pytest.raises(LibreOfficeMissingError, match="Install LibreOffice"):
        LibreOfficeMeasurer("no-such-soffice-binary").render(sample_resumes.styled())


def test_the_bottom_margin_is_read_from_the_document() -> None:
    assert bottom_margin_pt(sample_resumes.styled()) == 72  # python-docx's default: 1 inch
    assert bottom_margin_pt(b"not a docx") == 0


@needs_soffice
def test_pages_are_measured_as_a_fraction() -> None:
    measurer = LibreOfficeMeasurer()
    short = measurer.render(sample_resumes.styled())
    long = measurer.render(sample_resumes.styled(long=True))
    assert short.pdf.startswith(b"%PDF")
    assert short.page_count == 1 and 0.3 < short.pages < 1
    assert long.page_count == 2 and 1 < long.pages < 2


@needs_soffice
def test_a_footer_does_not_make_the_last_page_look_full() -> None:
    measurer = LibreOfficeMeasurer()
    plain = measurer.render(sample_resumes.styled())
    footed = measurer.render(with_footer(sample_resumes.styled()))
    assert footed.pages == pytest.approx(plain.pages, abs=0.05)
