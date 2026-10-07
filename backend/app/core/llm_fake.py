"""A stand-in for LLMClient so tests (and E2E runs) never need a real model."""

from collections import deque
from collections.abc import Callable, Iterable
from typing import TypeVar

from pydantic import BaseModel

from app.core.llm import LLMInvalidResponseError

T = TypeVar("T", bound=BaseModel)

# A canned reply: a fixed string, or a function of the prompt.
Reply = str | Callable[[str], str]


class FakeLLMClient:
    """Returns queued replies in order; records every prompt it was sent."""

    model = "fake-model"

    def __init__(self, replies: Iterable[Reply] = (), *, default: Reply | None = None) -> None:
        self.replies: deque[Reply] = deque(replies)
        self.default = default
        self.prompts: list[str] = []
        self.check_error: Exception | None = None

    def queue(self, *replies: Reply) -> None:
        self.replies.extend(replies)

    async def complete(
        self, prompt: str, *, system: str | None = None, temperature: float = 0
    ) -> str:
        self.prompts.append(prompt)
        reply = self.replies.popleft() if self.replies else self.default
        if reply is None:
            raise AssertionError("FakeLLMClient has no reply queued for this prompt")
        return reply(prompt) if callable(reply) else reply

    async def complete_json(
        self, prompt: str, schema: type[T], *, system: str | None = None, temperature: float = 0
    ) -> T:
        raw = await self.complete(prompt, system=system, temperature=temperature)
        try:
            return schema.model_validate_json(raw)
        except ValueError as exc:
            raise LLMInvalidResponseError(f"Fake reply didn't match {schema.__name__}") from exc

    async def check(self) -> None:
        if self.check_error is not None:
            raise self.check_error
