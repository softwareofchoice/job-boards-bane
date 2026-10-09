"""Measuring a resume's length by rendering it to PDF with LibreOffice (RND-3.8, R-D4)."""

import io
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pdfplumber
from docx import Document

from app.core.errors import AppError, ServiceUnavailableError


class LibreOfficeMissingError(ServiceUnavailableError):
    code = "libreoffice_missing"


class ConversionError(AppError):
    status_code = 500
    code = "conversion_failed"


@dataclass(frozen=True)
class Rendered:
    pdf: bytes
    page_count: int
    # Pages as a fraction: whole pages before the last, plus how far down the last page the
    # text reaches. 1.4 means one full page and text down to 40% of the second.
    pages: float


class PageMeasurer(Protocol):
    def render(self, docx: bytes) -> Rendered: ...


def bottom_margin_pt(docx: bytes) -> float:
    """The last section's bottom margin: footers (page numbers) sit inside it."""
    try:
        margin = Document(io.BytesIO(docx)).sections[-1].bottom_margin
    except Exception:  # not readable as .docx: measure without it
        return 0.0
    return float(margin.pt) if margin is not None else 0.0


def measure_pdf(pdf: bytes, ignore_bottom_pt: float = 0.0) -> tuple[int, float]:
    """Page count, and pages as a fraction. Text in the bottom `ignore_bottom_pt` points of the
    last page (a footer) doesn't count as content."""
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        count = len(doc.pages)
        if count == 0:
            return 0, 0.0
        last = doc.pages[-1]
        height = float(last.height)
        limit = height - ignore_bottom_pt
        bottoms = [float(w["bottom"]) for w in last.extract_words() if float(w["top"]) < limit]
        fill = max(bottoms) / height if bottoms else 0.0
    return count, round(count - 1 + min(fill, 1.0), 2)


class LibreOfficeMeasurer:
    """Runs `soffice --headless --convert-to pdf`. One conversion at a time: they share a profile
    directory, which makes every conversion after the first much faster."""

    _lock = threading.Lock()

    def __init__(self, soffice: str = "soffice", timeout_s: float = 120) -> None:
        self.soffice = soffice
        self.timeout_s = timeout_s
        self._profile = Path(tempfile.gettempdir()) / "bane-soffice-profile"

    def render(self, docx: bytes) -> Rendered:
        binary = shutil.which(self.soffice)
        if binary is None:
            raise LibreOfficeMissingError(
                "LibreOffice is needed to measure and export resumes, but `soffice` wasn't "
                f"found ({self.soffice}). Install LibreOffice or set SOFFICE_PATH."
            )
        with self._lock, tempfile.TemporaryDirectory(prefix="bane-render-") as tmp:
            source = Path(tmp) / "resume.docx"
            source.write_bytes(docx)
            command = [
                binary,
                f"-env:UserInstallation={self._profile.as_uri()}",
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp,
                str(source),
            ]
            try:
                subprocess.run(command, capture_output=True, timeout=self.timeout_s, check=True)
            except subprocess.TimeoutExpired as exc:
                raise ConversionError("LibreOffice took too long to convert the resume.") from exc
            except subprocess.CalledProcessError as exc:
                detail = exc.stderr.decode(errors="replace").strip()[:200]
                raise ConversionError(f"LibreOffice couldn't convert the resume: {detail}") from exc
            target = Path(tmp) / "resume.pdf"
            if not target.is_file():
                raise ConversionError("LibreOffice didn't produce a PDF for the resume.")
            pdf = target.read_bytes()
        count, pages = measure_pdf(pdf, bottom_margin_pt(docx))
        return Rendered(pdf=pdf, page_count=count, pages=pages)
