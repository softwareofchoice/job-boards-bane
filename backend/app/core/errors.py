import logging
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class AppError(Exception):
    """A known error with a status code and a message that is safe to show the user."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        # Extra fields the UI can act on, e.g. the id of the entry a duplicate clashes with.
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class UploadTooLargeError(AppError):
    status_code = 413
    code = "upload_too_large"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


def error_body(code: str, message: str, **details: Any) -> dict[str, dict[str, Any]]:
    return {
        "error": {"code": code, "message": message, "request_id": request_id_var.get(), **details}
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=error_body(exc.code, exc.message, **exc.details)
        )


def unexpected_error_response(request: Request) -> JSONResponse:
    """FND-5.2: log the details, show the user only a generic message and the request ID."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_body("internal_error", "Something went wrong. Please try again."),
    )
