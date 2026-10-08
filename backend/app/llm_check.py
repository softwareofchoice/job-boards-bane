"""Checks the local LLM end to end with a real scoring call (`make llm-check`).

Runs the Web Job Scraper's scoring prompt on a realistic, long posting a few times and reports
whether every reply was valid, how long calls take, how much of the context window the prompt
uses, whether repeated runs agree, and how much of the model sits on the GPU. Use it to confirm a
new setup works, or to compare models: `make llm-check MODEL=qwen2.5:7b`.
"""

import argparse
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.core.errors import AppError
from app.core.llm import LLMClient
from app.scraper.schemas import JobLevel, RawPosting, SearchOptions
from app.scraper.scorer import Score, Weights, score_posting

SAMPLE_OPTIONS = SearchOptions(
    job_title="Backend Engineer",
    location="Austin, TX",
    days_since_posting=7,
    skills=["Python", "PostgreSQL", "FastAPI", "AWS", "Kubernetes"],
    years_experience=5,
    job_level=JobLevel.SENIOR,
    jobs_pulled=10,
    jobs_selected=3,
)

_RESPONSIBILITIES = [
    "Design, build and operate Python services that handle millions of requests a day.",
    "Own our PostgreSQL schema design, query performance and migrations.",
    "Build REST APIs with FastAPI and document them for internal and partner teams.",
    "Run services on Kubernetes in AWS, including observability and on-call.",
    "Review code, mentor engineers and help set technical direction for the team.",
    "Work with product and design to break large projects into shippable pieces.",
]
_REQUIREMENTS = [
    "5+ years of professional software engineering experience, mostly backend.",
    "Strong Python and SQL; experience tuning PostgreSQL in production.",
    "Experience with containers and Kubernetes; AWS or another major cloud.",
    "Clear written communication; comfortable in a remote-friendly team.",
    "Nice to have: Kafka, Terraform, experience in fintech or payments.",
]
_ABOUT = (
    "Acme Payments builds the infrastructure that lets small businesses take card payments "
    "online and in person. We're a team of 180 people across Austin and remote US locations, "
    "and our platform processes over $4B a year. Our engineering culture values small, "
    "frequent releases, thoughtful code review and owning what you build in production. "
)


def _long_description() -> str:
    """About 5,500 characters: close to the scorer's 6,000-character limit, like a long posting."""
    parts = [_ABOUT]
    while sum(len(p) for p in parts) < 5500:
        parts.append("Responsibilities:\n- " + "\n- ".join(_RESPONSIBILITIES))
        parts.append("Requirements:\n- " + "\n- ".join(_REQUIREMENTS))
        parts.append(_ABOUT)
    return "\n\n".join(parts)[:5600]


SAMPLE_POSTING = RawPosting(
    title="Senior Backend Engineer (Python)",
    company="Acme Payments",
    location="Austin, TX (hybrid)",
    url="https://jobs.example.test/acme/123",
    posted_text="2 days ago",
    description=_long_description(),
)


@dataclass
class RunResult:
    seconds: float
    score: Score | None = None
    error: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class CheckReport:
    model: str
    num_ctx: int
    runs: list[RunResult]
    gpu_share: float | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def gpu_share(loaded: list[dict[str, Any]], model: str) -> float | None:
    """Fraction of the model's memory on the GPU, from Ollama's `/api/ps` (None if unknown)."""
    wanted = model if ":" in model else f"{model}:latest"
    for entry in loaded:
        if entry.get("name") == wanted or entry.get("model") == wanted:
            size, vram = entry.get("size"), entry.get("size_vram")
            if isinstance(size, int) and isinstance(vram, int) and size > 0:
                return vram / size
    return None


async def run_check(client: LLMClient, *, runs: int, max_chars: int) -> CheckReport:
    report = CheckReport(model=client.model, num_ctx=client.num_ctx, runs=[])
    try:
        await client.check()
    except AppError as exc:
        report.problems.append(exc.message)
        return report

    for _ in range(runs):
        start = time.perf_counter()
        try:
            score = await score_posting(
                client, SAMPLE_OPTIONS, SAMPLE_POSTING, weights=Weights(), max_chars=max_chars
            )
            result = RunResult(time.perf_counter() - start, score=score)
        except AppError as exc:
            result = RunResult(time.perf_counter() - start, error=exc.message)
        result.usage = dict(client.last_usage)
        report.runs.append(result)

    failed = [r for r in report.runs if r.error]
    if failed:
        report.problems.append(f"{len(failed)} of {runs} scoring calls failed: {failed[0].error}")

    prompt_tokens = max((r.usage.get("prompt_eval_count", 0) for r in report.runs), default=0)
    if prompt_tokens >= client.num_ctx * 0.95:
        report.problems.append(
            f"The prompt used {prompt_tokens} tokens, at the {client.num_ctx}-token context "
            "window: it was probably cut short. Raise LLM_NUM_CTX."
        )

    try:
        report.gpu_share = gpu_share(await client.loaded_models(), client.model)
    except AppError:
        report.gpu_share = None
    return report


def format_report(report: CheckReport) -> str:
    lines = [f"Model: {report.model}   context window: {report.num_ctx} tokens"]
    for i, run in enumerate(report.runs, start=1):
        if run.score is None:
            lines.append(f"  run {i}: FAILED after {run.seconds:.1f}s: {run.error}")
            continue
        sub = run.score.sub_scores
        tokens = run.usage.get("prompt_eval_count")
        load = run.usage.get("load_duration", 0) / 1e9
        lines.append(
            f"  run {i}: {run.seconds:5.1f}s"
            + (f" (incl. {load:.1f}s loading the model)" if load >= 1 else "")
            + f"  score {run.score.overall:3d}  title {sub.title_fit} exp {sub.experience}"
            f" level {sub.level} loc {sub.location} skills {sub.skills}"
            + (f"  prompt {tokens} tokens" if tokens else "")
        )
    scored = [r.score for r in report.runs if r.score is not None]
    if scored:
        lines.append(f"  rationale: {scored[0].rationale}")
        overall = {s.overall for s in scored}
        lines.append(
            "  repeat runs agree"
            if len(overall) == 1
            else f"  repeat runs differ: {sorted(overall)} (expected the same at temperature 0)"
        )
    if not report.runs:
        pass  # Never reached the model, so there's nothing to say about the GPU.
    elif report.gpu_share is None:
        lines.append("GPU: unknown (model not listed by `ollama ps`)")
    else:
        pct = round(report.gpu_share * 100)
        hint = "" if pct >= 100 else "  <- part runs on the CPU; try a smaller model or LLM_NUM_CTX"
        lines.append(f"GPU: {pct}% of the model is on the GPU{hint}")
    lines.extend(f"PROBLEM: {p}" for p in report.problems)
    lines.append("OK" if report.ok else "FAILED")
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="model to test (default: LLM_MODEL)")
    parser.add_argument("--runs", type=int, default=3, help="scoring calls to make (default 3)")
    args = parser.parse_args()

    settings = get_settings()
    if settings.llm_fake:
        print("LLM_FAKE is on, so the app isn't using a real model. Unset it to run this check.")
        return 1
    client = LLMClient(
        settings.llm_base_url,
        args.model or settings.llm_model,
        timeout_s=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        num_ctx=settings.llm_num_ctx,
    )
    print(f"Scoring a {len(SAMPLE_POSTING.description)}-character posting {args.runs} times…")
    report = await run_check(client, runs=max(1, args.runs), max_chars=settings.scorer_max_chars)
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
