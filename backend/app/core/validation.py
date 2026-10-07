"""Collect field errors from several checks and report them together as one 422 (FND-5.1)."""

from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError


class FieldErrors:
    """Gathers `{field: message}` errors in FastAPI's 422 format, so forms can show them all."""

    def __init__(self) -> None:
        self._errors: list[dict[str, Any]] = []

    def add(self, field: str, message: str) -> None:
        self._errors.append({"type": "value_error", "loc": ("body", field), "msg": message})

    def validate[M: BaseModel](self, model: type[M], data: dict[str, Any]) -> M | None:
        """Validate `data`; record any errors and return None if it's invalid."""
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            for err in exc.errors(include_url=False, include_context=False):
                self._errors.append({**err, "loc": ("body", *err["loc"])})
            return None

    def raise_if_any(self) -> None:
        if self._errors:
            raise RequestValidationError(self._errors)
