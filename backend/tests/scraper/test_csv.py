import csv
import io
from datetime import date

from app.scraper.csv_export import COLUMNS, safe_cell, to_csv
from app.scraper.models import ScrapedPosting


def row(**overrides: object) -> ScrapedPosting:
    data: dict[str, object] = {
        "position": 0,
        "title": "Dev",
        "company": "Acme",
        "location": "Austin, TX",
        "url": "https://x.test/1",
        "via": "LinkedIn",
        "salary_text": None,
        "posted_text": "2 days ago",
        "posted_at": date(2026, 10, 6),
        "description": "d",
        "score": 87,
        "sub_scores": {"title_fit": 9, "skills": 8, "experience": 7, "level": 9, "location": 10},
        "matched_skills": ["Python", "AWS"],
        "missing_skills": ["Go"],
        "rationale": "Strong.",
        "rank": 1,
        "selected": True,
    }
    data.update(overrides)
    return ScrapedPosting(**data)


def test_csv_columns_bom_and_values() -> None:
    text = to_csv(
        [
            row(),
            row(
                rank=None,
                score=None,
                sub_scores=None,
                posted_at=None,
                posted_text=None,
                rationale=None,
            ),
        ]
    )
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert rows[0] == COLUMNS
    first = dict(zip(COLUMNS, rows[1], strict=True))
    assert first["rank"] == "1"
    assert first["score"] == "87"
    assert first["posted_date"] == "2026-10-06"
    assert first["matched_skills"] == "Python; AWS"
    assert first["level_score"] == "9"
    second = dict(zip(COLUMNS, rows[2], strict=True))
    assert second["score"] == "" and second["title_fit"] == "" and second["posted_date"] == ""


def test_formula_injection_is_neutralised() -> None:
    assert safe_cell('=HYPERLINK("http://evil")') == '\'=HYPERLINK("http://evil")'
    assert safe_cell("+1") == "'+1"
    assert safe_cell("-cmd") == "'-cmd"
    assert safe_cell("@SUM(A1)") == "'@SUM(A1)"
    assert safe_cell("Normal text") == "Normal text"
    text = to_csv([row(company="=evil()")])
    assert "'=evil()" in text
