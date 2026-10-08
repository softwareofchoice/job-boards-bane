import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import BaseModel

from app.core.llm import (
    LLMClient,
    LLMInvalidResponseError,
    LLMModelMissingError,
    LLMUnavailableError,
)


class Score(BaseModel):
    score: int
    reason: str


Handler = Callable[[httpx.Request], httpx.Response]


def chat_reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def make_client(handler: Handler, max_retries: int = 2) -> LLMClient:
    return LLMClient(
        "http://llm.test",
        "llama3.1:8b",
        max_retries=max_retries,
        transport=httpx.MockTransport(handler),
    )


async def test_complete_sends_system_and_user_messages() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return chat_reply("hello")

    result = await make_client(handler).complete("Hi", system="Be brief")
    assert result == "hello"
    body = sent[0]
    assert body["model"] == "llama3.1:8b"
    assert body["stream"] is False
    assert body["messages"] == [
        {"role": "system", "content": "Be brief"},
        {"role": "user", "content": "Hi"},
    ]
    assert body["options"] == {"num_ctx": 8192, "temperature": 0}


async def test_complete_json_retries_after_invalid_reply() -> None:
    replies = iter(["not json", '{"score": 7, "reason": "good fit"}'])
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return chat_reply(next(replies))

    result = await make_client(handler).complete_json("Rate it", Score)

    assert result == Score(score=7, reason="good fit")
    assert len(sent) == 2
    assert sent[0]["format"] == Score.model_json_schema()
    retry_messages = sent[1]["messages"]
    assert isinstance(retry_messages, list)
    assert retry_messages[-2] == {"role": "assistant", "content": "not json"}
    assert "not valid" in retry_messages[-1]["content"]


async def test_complete_json_gives_up_after_max_retries() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return chat_reply('{"score": "high"}')

    with pytest.raises(LLMInvalidResponseError):
        await make_client(handler, max_retries=1).complete_json("Rate it", Score)
    assert calls == 2


async def test_connection_refused_is_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(LLMUnavailableError, match="ollama serve"):
        await make_client(handler).complete("Hi")


async def test_unknown_model_is_model_missing_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'llama3.1:8b' not found"})

    with pytest.raises(LLMModelMissingError, match=r"ollama pull llama3\.1:8b"):
        await make_client(handler).complete("Hi")


async def test_server_error_is_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "out of memory"})

    with pytest.raises(LLMUnavailableError, match="out of memory"):
        await make_client(handler).complete("Hi")


@pytest.mark.parametrize(
    ("models", "configured", "error"),
    [
        (["llama3.1:8b"], "llama3.1:8b", None),
        (["mistral:latest"], "mistral", None),
        (["mistral:latest"], "llama3.1:8b", LLMModelMissingError),
    ],
)
async def test_check(models: list[str], configured: str, error: type[Exception] | None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": m} for m in models]})

    client = LLMClient("http://llm.test", configured, transport=httpx.MockTransport(handler))
    if error is None:
        await client.check()
    else:
        with pytest.raises(error):
            await client.check()


async def test_check_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LLMUnavailableError):
        await make_client(handler).check()


async def test_context_window_is_configurable_and_usage_is_recorded() -> None:
    sent: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "ok"},
                "prompt_eval_count": 812,
                "eval_count": 40,
                "total_duration": 1_500_000_000,
            },
        )

    client = LLMClient(
        "http://llm.test", "llama3.1:8b", num_ctx=4096, transport=httpx.MockTransport(handler)
    )
    await client.complete("Hi", temperature=0.5)

    assert sent[0]["options"] == {"num_ctx": 4096, "temperature": 0.5}
    assert client.last_usage == {
        "prompt_eval_count": 812,
        "eval_count": 40,
        "total_duration": 1_500_000_000,
    }
