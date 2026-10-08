"""Client for the local LLM server (Ollama) shared by the scraper and Resume Rounder (FND-3)."""

import json
import logging
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.errors import AppError, ServiceUnavailableError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Message = dict[str, str]


class LLMUnavailableError(ServiceUnavailableError):
    code = "llm_unavailable"


class LLMModelMissingError(ServiceUnavailableError):
    code = "llm_model_missing"


class LLMInvalidResponseError(AppError):
    status_code = 502
    code = "llm_invalid_response"


class LLM(Protocol):
    model: str

    async def complete(
        self, prompt: str, *, system: str | None = None, temperature: float = 0
    ) -> str: ...

    async def complete_json(
        self, prompt: str, schema: type[T], *, system: str | None = None, temperature: float = 0
    ) -> T: ...

    async def check(self) -> None:
        """Raise LLMUnavailableError / LLMModelMissingError if the model can't be used."""
        ...


class LLMClient:
    """Talks to Ollama's chat API. Every request stays on the local machine (FND-3.1)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_s: float = 120,
        max_retries: int = 2,
        num_ctx: int = 8192,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        # The context window, in tokens. Set explicitly because Ollama's default depends on its
        # version and can be as small as 2048, which would silently cut long prompts short.
        self.num_ctx = num_ctx
        # Token counts and timings Ollama reported for the most recent reply (for llm-check).
        self.last_usage: dict[str, int] = {}
        self._transport = transport

    async def complete(
        self, prompt: str, *, system: str | None = None, temperature: float = 0
    ) -> str:
        return await self._chat(_messages(prompt, system), temperature=temperature)

    async def complete_json(
        self, prompt: str, schema: type[T], *, system: str | None = None, temperature: float = 0
    ) -> T:
        """Ask for JSON matching `schema`; re-prompt with the validation error on bad output."""
        messages = _messages(prompt, system)
        json_schema = schema.model_json_schema()
        last_error = ""
        for attempt in range(self.max_retries + 1):
            reply = await self._chat(messages, temperature=temperature, format=json_schema)
            try:
                return schema.model_validate_json(reply)
            except ValidationError as exc:
                last_error = _short_error(exc)
                logger.warning(
                    "LLM reply failed validation (attempt %d/%d): %s",
                    attempt + 1,
                    self.max_retries + 1,
                    last_error,
                )
                messages = [
                    *messages,
                    {"role": "assistant", "content": reply},
                    {
                        "role": "user",
                        "content": (
                            f"That reply was not valid: {last_error}. Reply again with only "
                            "JSON that matches the schema."
                        ),
                    },
                ]
        raise LLMInvalidResponseError(
            f"The local model didn't return valid output after {self.max_retries + 1} "
            f"attempts ({last_error})."
        )

    async def check(self) -> None:
        async with self._client() as client:
            try:
                response = await client.get("/api/tags")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise self._unavailable() from exc
        names = {m.get("name") for m in response.json().get("models", [])}
        # Ollama reports "llama3.1:8b"; a model configured without a tag means ":latest".
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        if wanted not in names:
            raise self._model_missing()

    async def loaded_models(self) -> list[dict[str, Any]]:
        """Models Ollama has in memory (`/api/ps`), including how much of each is on the GPU."""
        async with self._client() as client:
            try:
                response = await client.get("/api/ps")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise self._unavailable() from exc
        models = response.json().get("models", [])
        return [m for m in models if isinstance(m, dict)]

    async def _chat(self, messages: list[Message], **options: Any) -> str:
        fmt = options.pop("format", None)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": self.num_ctx, **options},
        }
        if fmt is not None:
            body["format"] = fmt
        async with self._client() as client:
            try:
                response = await client.post("/api/chat", json=body)
            except httpx.TransportError as exc:
                raise self._unavailable() from exc
        if response.status_code == 404:
            raise self._model_missing()
        if response.is_error:
            raise LLMUnavailableError(
                f"The local LLM server returned HTTP {response.status_code}: "
                f"{_error_text(response)}"
            )
        try:
            data = response.json()
            content = str(data["message"]["content"])
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMInvalidResponseError("The local LLM server sent an unexpected reply.") from exc
        self.last_usage = {
            key: int(data[key])
            for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration")
            if isinstance(data.get(key), int)
        }
        return content

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout_s, transport=self._transport
        )

    def _unavailable(self) -> LLMUnavailableError:
        return LLMUnavailableError(
            f"Can't reach the local LLM server at {self.base_url}. "
            "Start it with `ollama serve` (or `make llm-up`)."
        )

    def _model_missing(self) -> LLMModelMissingError:
        return LLMModelMissingError(
            f"The model {self.model!r} isn't installed. Run `ollama pull {self.model}`."
        )


def _messages(prompt: str, system: str | None) -> list[Message]:
    messages = [{"role": "system", "content": system}] if system else []
    return [*messages, {"role": "user", "content": prompt}]


def _short_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


def _error_text(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", response.text))[:200]
    except (ValueError, json.JSONDecodeError):
        return response.text[:200]
