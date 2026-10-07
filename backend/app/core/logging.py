import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.core.errors import request_id_var, unexpected_error_response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _AppHandler(logging.StreamHandler):  # type: ignore[type-arg]
    pass


def configure_logging(level: int = logging.INFO) -> None:
    """Log to stderr with the request ID on every line. Safe to call more than once."""
    root = logging.getLogger()
    root.setLevel(level)
    if any(isinstance(h, _AppHandler) for h in root.handlers):
        return
    handler = _AppHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    root.addHandler(handler)


def add_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        try:
            try:
                response = await call_next(request)
            except Exception:
                # Handled here rather than by an exception handler so the log line and the
                # response both still carry the request ID.
                response = unexpected_error_response(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = rid
        return response
