"""Reading and editing the template resume (.docx) (RND-2.5, RND-3.5, RND-3.6).

The document is seen as one list of paragraphs in reading order, including those inside table
cells. Indexes into that list identify paragraphs. The only edits ever made are to the text of
bullet paragraphs inside the experience section; everything else is left byte-for-byte alone,
and `changes_outside_bullets` checks that.
"""

import copy
import hashlib
import io
import re
from dataclasses import dataclass, field
from typing import Any, cast

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Length
from docx.styles.style import ParagraphStyle
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from app.core.errors import AppError

EXPERIENCE_RE = re.compile(
    r"^((professional|work|relevant) )?experience$|^employment( history)?$|^(work|career) history$",
    re.IGNORECASE,
)
# Characters people type at the start of a line to make a bullet by hand.
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[•·‣▪▫◦●○■□➢►✓*]|[-\u2013\u2014](?=\s))\s*")
MAX_HEADING_CHARS = 60
MAX_HEADING_WORDS = 6

_W14 = "http://schemas.microsoft.com/office/word/2010/wordml"


class InvalidTemplateError(AppError):
    status_code = 422
    code = "invalid_template"


class ExperienceSectionNotFoundError(AppError):
    """RND-2.5: no heading looks like the experience section; the user picks one."""

    status_code = 422
    code = "experience_not_found"

    def __init__(self, headings: list["Heading"]) -> None:
        super().__init__(
            "Couldn't find the experience section in this resume. Choose its heading.",
            headings=[{"index": h.index, "text": h.text} for h in headings],
        )
        self.headings = headings


@dataclass(frozen=True)
class Heading:
    index: int
    text: str


@dataclass
class ExperienceEntry:
    header_idxs: list[int]  # role / company / dates lines: never edited
    header_text: str
    bullet_idxs: list[int]  # the only paragraphs that get rewritten
    bullets: list[str]  # bullet text without any typed bullet character

    @property
    def chars(self) -> int:
        return sum(len(b) for b in self.bullets)


@dataclass
class ResumeModel:
    heading_idx: int
    end_idx: int  # index of the next section heading (or the paragraph count)
    entries: list[ExperienceEntry]
    headings: list[Heading]
    total_chars: int  # text in the whole document, to turn characters into pages
    warnings: list[str] = field(default_factory=list)

    @property
    def bullet_chars(self) -> int:
        return sum(e.chars for e in self.entries)


def load(data: bytes) -> DocxDocument:
    try:
        return Document(io.BytesIO(data))
    except Exception as exc:  # zipfile, KeyError and python-docx's own package errors
        raise InvalidTemplateError(
            "This file couldn't be read as a Word (.docx) document."
        ) from exc


def paragraphs(doc: DocxDocument) -> list[Paragraph]:
    """Every paragraph in reading order, including table cells but not text boxes."""
    found = []
    for p in doc.element.body.iter(qn("w:p")):
        if any(a.tag == qn("w:txbxContent") for a in p.iterancestors()):
            continue
        found.append(Paragraph(p, doc._body))
    return found


# --- Recognising headings and bullets --------------------------------------------------------


def _style_chain(style: Any) -> list[ParagraphStyle]:
    chain: list[ParagraphStyle] = []
    while style is not None and len(chain) < 20:
        chain.append(style)
        style = style.base_style
    return chain


def _style(p: Paragraph) -> ParagraphStyle | None:
    try:
        return p.style
    except (KeyError, ValueError):
        return None


def heading_level(p: Paragraph) -> int | None:
    for style in _style_chain(_style(p)):
        match = re.fullmatch(r"heading (\d)", (style.name or "").lower())
        if match:
            return int(match.group(1))
    return None


def _text_runs(p: Paragraph) -> list[Run]:
    return [r for r in p.runs if r.text.strip()]


def _style_font(p: Paragraph, attr: str) -> Any:
    for style in _style_chain(_style(p)):
        value = getattr(style.font, attr)
        if value is not None:
            return value
    return None


def _is_bold(p: Paragraph) -> bool:
    runs = _text_runs(p)
    if not runs:
        return False
    style_bold = bool(_style_font(p, "bold"))
    return all(r.bold if r.bold is not None else style_bold for r in runs)


def _is_caps(p: Paragraph) -> bool:
    text = p.text
    if any(c.isalpha() for c in text) and text == text.upper():
        return True
    runs = _text_runs(p)
    style_caps = bool(_style_font(p, "all_caps"))
    return bool(runs) and all(
        r.font.all_caps if r.font.all_caps is not None else style_caps for r in runs
    )


def _font_size(p: Paragraph) -> Length | None:
    for run in _text_runs(p):
        if run.font.size is not None:
            return run.font.size
    return cast(Length | None, _style_font(p, "size"))


def is_bullet(p: Paragraph) -> bool:
    ppr = p._p.pPr
    if ppr is not None and ppr.numPr is not None:
        num_id = cast(Any, ppr.numPr).numId
        # numId 0 means "numbering switched off" for this paragraph.
        return num_id is None or num_id.val != 0
    for style in _style_chain(_style(p)):
        style_ppr = style.element.pPr
        if style_ppr is not None and style_ppr.numPr is not None:
            return True
    return bool(BULLET_PREFIX_RE.match(p.text)) and bool(BULLET_PREFIX_RE.sub("", p.text).strip())


def looks_like_heading(p: Paragraph) -> bool:
    text = p.text.strip()
    if not text or len(text) > MAX_HEADING_CHARS or len(text.split()) > MAX_HEADING_WORDS:
        return False
    if is_bullet(p):
        return False
    return heading_level(p) is not None or _is_bold(p) or _is_caps(p)


def _signature(p: Paragraph) -> tuple[Any, ...]:
    """How a heading is formatted. A section ends at the next heading formatted the same way."""
    style = _style(p)
    return (style.name if style else None, _is_bold(p), _is_caps(p), _font_size(p))


def _ends_section(p: Paragraph, heading: Paragraph) -> bool:
    if not looks_like_heading(p):
        return False
    level = heading_level(heading)
    if level is not None:
        other = heading_level(p)
        return other is not None and other <= level
    return _signature(p) == _signature(heading)


def _normalise_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(":").strip()


def bullet_prefix(text: str) -> str:
    match = BULLET_PREFIX_RE.match(text)
    return match.group(0) if match else ""


# --- Reading ---------------------------------------------------------------------------------


def read_resume(data: bytes, heading_idx: int | None = None) -> ResumeModel:
    return read_document(load(data), heading_idx)


def read_document(doc: DocxDocument, heading_idx: int | None = None) -> ResumeModel:
    """Find the experience section and split it into entries (RND-2.5).

    `heading_idx` overrides the search with a heading the user chose.
    """
    paras = paragraphs(doc)
    headings = [Heading(i, p.text.strip()) for i, p in enumerate(paras) if looks_like_heading(p)]
    if heading_idx is None:
        heading_idx = next(
            (h.index for h in headings if EXPERIENCE_RE.match(_normalise_heading(h.text))), None
        )
        if heading_idx is None:
            raise ExperienceSectionNotFoundError(headings)
    elif not 0 <= heading_idx < len(paras) or not paras[heading_idx].text.strip():
        raise ExperienceSectionNotFoundError(headings)

    heading = paras[heading_idx]
    end_idx = next(
        (i for i in range(heading_idx + 1, len(paras)) if _ends_section(paras[i], heading)),
        len(paras),
    )

    entries: list[ExperienceEntry] = []
    current: ExperienceEntry | None = None
    for i in range(heading_idx + 1, end_idx):
        p = paras[i]
        text = p.text.strip()
        if not text:
            continue  # spacing
        if is_bullet(p):
            if current is None:
                current = ExperienceEntry([], "", [], [])
                entries.append(current)
            current.bullet_idxs.append(i)
            current.bullets.append(BULLET_PREFIX_RE.sub("", p.text).strip())
            continue
        if current is None or current.bullet_idxs:
            current = ExperienceEntry([], "", [], [])
            entries.append(current)
        current.header_idxs.append(i)
        current.header_text = f"{current.header_text} · {text}" if current.header_text else text

    warnings = []
    section = [paras[i]._p for i in range(heading_idx, end_idx)]
    if any(any(a.tag == qn("w:tbl") for a in p.iterancestors()) for p in section):
        warnings.append(
            "Your experience section is laid out in a table. Check the layout of the result."
        )
    if any(p.find(".//" + qn("w:txbxContent")) is not None for p in section):
        warnings.append("Text boxes in the experience section aren't changed.")
    if not any(e.bullets for e in entries):
        warnings.append("No bullet points were found in the experience section.")

    return ResumeModel(
        heading_idx=heading_idx,
        end_idx=end_idx,
        entries=entries,
        headings=headings,
        total_chars=sum(len(p.text) for p in paras),
        warnings=warnings,
    )


# --- Writing ---------------------------------------------------------------------------------


def _first_text_run(p: Any) -> Any:
    """The run holding the bullet's own text (skipping a typed bullet character)."""
    runs = [r for r in p.iter(qn("w:r")) if r.find(qn("w:t")) is not None]
    for run in runs:
        text = "".join(t.text or "" for t in run.iter(qn("w:t")))
        if BULLET_PREFIX_RE.sub("", text).strip():
            return run
    return runs[0] if runs else None


def set_paragraph_text(p: Any, text: str) -> None:
    """Replace a paragraph's text, keeping its `pPr` and the formatting of its first run."""
    run = _first_text_run(p)
    rpr = run.find(qn("w:rPr")) if run is not None else None
    rpr = copy.deepcopy(rpr) if rpr is not None else None
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)
    new_run = OxmlElement("w:r")
    if rpr is not None:
        new_run.append(rpr)
    for i, part in enumerate(text.split("\t")):
        if i:
            new_run.append(OxmlElement("w:tab"))
        if part:
            t = OxmlElement("w:t")
            t.text = part
            t.set(qn("xml:space"), "preserve")
            new_run.append(t)
    p.append(new_run)


def _drop_ids(p: Any) -> None:
    """A copied paragraph must not reuse Word's paragraph ids."""
    for name in ("paraId", "textId"):
        p.attrib.pop(f"{{{_W14}}}{name}", None)


def write_resume(data: bytes, model: ResumeModel, new_bullets: dict[int, list[str]]) -> bytes:
    """A copy of the template with the bullets of the given entries replaced (RND-3.5, 3.6).

    `new_bullets` maps an entry's position in `model.entries` to its new bullet texts.
    Extra bullets are copies of the entry's last bullet; surplus bullets are removed.
    """
    doc = load(data)
    paras = paragraphs(doc)
    for entry_no, texts in new_bullets.items():
        entry = model.entries[entry_no]
        if not entry.bullet_idxs or not texts:
            continue
        elements = [paras[i]._p for i in entry.bullet_idxs]
        prefixes = [bullet_prefix(paras[i].text) for i in entry.bullet_idxs]
        pattern = copy.deepcopy(elements[-1])
        anchor = None
        for k, text in enumerate(texts):
            if k < len(elements):
                set_paragraph_text(elements[k], prefixes[k] + text)
                anchor = elements[k]
            else:
                added = copy.deepcopy(pattern)
                _drop_ids(added)
                set_paragraph_text(added, prefixes[-1] + text)
                assert anchor is not None
                anchor.addnext(added)
                anchor = added
        for extra in elements[len(texts) :]:
            extra.getparent().remove(extra)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


# --- Checking --------------------------------------------------------------------------------


def _fingerprint(data: bytes, heading_idx: int) -> dict[str, str]:
    """Hashes of everything except the bullet paragraphs of the experience section."""
    doc = load(data)
    model = read_document(doc, heading_idx)
    bullet_idxs = {i for e in model.entries for i in e.bullet_idxs}
    body = copy.deepcopy(doc.element.body)
    copied = [
        p
        for p in body.iter(qn("w:p"))
        if not any(a.tag == qn("w:txbxContent") for a in p.iterancestors())
    ]
    for i in sorted(bullet_idxs, reverse=True):
        copied[i].getparent().remove(copied[i])
    hashes = {"document body": _sha(body.xml.encode())}
    for part in doc.part.package.iter_parts():
        if part is not doc.part:
            hashes[str(part.partname)] = _sha(part.blob)
    return hashes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def changes_outside_bullets(template: bytes, output: bytes, heading_idx: int) -> list[str]:
    """Parts of the document that differ outside the experience bullets (RND-3.5).

    Anything listed here is a bug in the writer, never something the user did.
    """
    before = _fingerprint(template, heading_idx)
    after = _fingerprint(output, heading_idx)
    return sorted(
        name for name in before.keys() | after.keys() if before.get(name) != after.get(name)
    )
