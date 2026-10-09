from pathlib import Path
from typing import Any

import pytest

from app import rounder_eval
from app.config import get_settings
from app.demo import demo_llm
from tests.rounder.helpers import EstimateMeasurer


async def test_eval_writes_a_report_for_every_posting_and_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rounder_eval, "LLMClient", lambda *a, **k: demo_llm())
    monkeypatch.setattr(rounder_eval, "LibreOfficeMeasurer", lambda *a: EstimateMeasurer())
    settings: Any = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    assert await rounder_eval.run(None, 1.0) == 0

    reports = sorted(tmp_path.glob("eval/*/*/report.md"))
    assert len(reports) == len(rounder_eval.POSTINGS) * len(rounder_eval.RESUMES)
    text = reports[0].read_text()
    assert "## Posting skills" in text and "Before:" in text and "After:" in text
