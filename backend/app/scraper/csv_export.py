"""CSV export of a run's postings (SCR-5.3)."""

import csv
import io
from collections.abc import Iterable

from app.scraper.models import ScrapedPosting

COLUMNS = [
    "rank",
    "score",
    "title",
    "company",
    "location",
    "posted_date",
    "url",
    "via",
    "salary",
    "matched_skills",
    "missing_skills",
    "title_fit",
    "skills_score",
    "experience_score",
    "level_score",
    "location_score",
    "rationale",
]

# Spreadsheet apps run cells starting with these as formulas.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: str | None) -> str:
    if not value:
        return ""
    return "'" + value if value.startswith(_FORMULA_PREFIXES) else value


def _number(value: int | None) -> str:
    return "" if value is None else str(value)


def to_csv(postings: Iterable[ScrapedPosting]) -> str:
    """UTF-8 with a BOM so Excel detects the encoding."""
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for p in postings:
        sub = p.sub_scores or {}
        writer.writerow(
            [
                _number(p.rank),
                _number(p.score),
                safe_cell(p.title),
                safe_cell(p.company),
                safe_cell(p.location),
                p.posted_at.isoformat() if p.posted_at else safe_cell(p.posted_text),
                safe_cell(p.url),
                safe_cell(p.via),
                safe_cell(p.salary_text),
                safe_cell("; ".join(p.matched_skills)),
                safe_cell("; ".join(p.missing_skills)),
                _number(sub.get("title_fit")),
                _number(sub.get("skills")),
                _number(sub.get("experience")),
                _number(sub.get("level")),
                _number(sub.get("location")),
                safe_cell(p.rationale),
            ]
        )
    return out.getvalue()
