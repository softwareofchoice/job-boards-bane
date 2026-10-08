import json
from typing import Any

import httpx

from app.core.llm import LLMClient
from app.llm_check import SAMPLE_POSTING, format_report, gpu_share, run_check

SCORE = {
    "title_fit": 9,
    "skills": 8,
    "experience": 8,
    "level": 9,
    "location": 10,
    "matched_skills": ["Python"],
    "missing_skills": [],
    "rationale": "Strong fit.",
}


def ollama(
    *,
    chat: list[Any] | None = None,
    models: list[str] | None = None,
    ps: list[dict[str, Any]] | None = None,
    prompt_tokens: int = 1800,
) -> httpx.MockTransport:
    """A fake Ollama: /api/tags, /api/ps and /api/chat (replies taken from `chat` in order)."""
    replies = list(chat or [])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            names = models if models is not None else ["llama3.1:8b"]
            return httpx.Response(200, json={"models": [{"name": n} for n in names]})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": ps or []})
        reply = replies.pop(0) if replies else SCORE
        content = reply if isinstance(reply, str) else json.dumps(reply)
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": content},
                "prompt_eval_count": prompt_tokens,
                "eval_count": 60,
                "load_duration": 3_000_000_000,
            },
        )

    return httpx.MockTransport(handler)


def client(transport: httpx.MockTransport, **kwargs: Any) -> LLMClient:
    return LLMClient("http://llm.test", "llama3.1:8b", transport=transport, **kwargs)


def test_sample_posting_is_long() -> None:
    assert 5000 <= len(SAMPLE_POSTING.description) <= 6000


async def test_healthy_model_on_gpu() -> None:
    ps = [{"name": "llama3.1:8b", "size": 6_000_000_000, "size_vram": 6_000_000_000}]
    report = await run_check(client(ollama(ps=ps)), runs=2, max_chars=6000)

    assert report.ok, report.problems
    assert len(report.runs) == 2
    assert report.gpu_share == 1.0
    text = format_report(report)
    assert "100% of the model is on the GPU" in text
    assert "repeat runs agree" in text
    assert "prompt 1800 tokens" in text
    assert "incl. 3.0s loading the model" in text
    assert text.endswith("OK")


async def test_missing_model_is_reported() -> None:
    report = await run_check(client(ollama(models=["qwen2.5:7b"])), runs=1, max_chars=6000)
    assert not report.ok
    assert "ollama pull llama3.1:8b" in report.problems[0]
    assert report.runs == []


async def test_invalid_replies_fail_the_check() -> None:
    transport = ollama(chat=["nope", "still nope"])
    report = await run_check(client(transport, max_retries=1), runs=1, max_chars=6000)
    assert not report.ok
    assert "1 of 1 scoring calls failed" in report.problems[0]
    assert "FAILED after" in format_report(report)


async def test_full_context_window_is_flagged() -> None:
    report = await run_check(
        client(ollama(prompt_tokens=2048), num_ctx=2048), runs=1, max_chars=6000
    )
    assert any("Raise LLM_NUM_CTX" in p for p in report.problems)


async def test_disagreeing_runs_are_noted() -> None:
    other = {**SCORE, "title_fit": 2}
    report = await run_check(client(ollama(chat=[SCORE, other])), runs=2, max_chars=6000)
    assert "repeat runs differ" in format_report(report)


def test_gpu_share() -> None:
    loaded = [
        {"name": "qwen2.5:7b", "size": 10, "size_vram": 10},
        {"name": "llama3.1:8b", "size": 8, "size_vram": 6},
    ]
    assert gpu_share(loaded, "llama3.1:8b") == 0.75
    assert gpu_share([{"name": "mistral:latest", "size": 4, "size_vram": 0}], "mistral") == 0.0
    assert gpu_share(loaded, "llama3.2:3b") is None
