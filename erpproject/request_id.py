"""
Request-ID middleware and logging filter.

For every HTTP request this middleware:

1. Reads an incoming ``X-Request-ID`` header (if any, trusted only when it
   looks like a sane token — short, ASCII, alphanumerics + dashes).  Otherwise
   it generates a new UUID4 hex string.
2. Stores the value on ``request.request_id`` so views can log it.
3. Stores it in a thread-local so the ``RequestIDFilter`` can inject it into
   every log record produced while that request is being handled, even from
   code (e.g. services, tasks) that does not have access to the request.
4. Echoes the value back to the client in the response ``X-Request-ID`` header
   so clients, load-balancers, and log aggregators can correlate requests with
   server logs.

The filter and middleware are deliberately dependency-free and safe to use in
production without Celery/Redis/newrelic configured.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid

_local = threading.local()

# Accept only short, ASCII, alnum + dash/underscore IDs.  Rejects anything that
# could cause log-injection (newlines, control chars, overly long strings).
_VALID_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def get_request_id() -> str:
    """Return the request id for the current thread, or ``'-'`` if none set."""
    return getattr(_local, "request_id", "-")


def _set_request_id(value: str) -> None:
    _local.request_id = value


def _clear_request_id() -> None:
    if hasattr(_local, "request_id"):
        del _local.request_id


class RequestIDMiddleware:
    """Middleware that attaches a request id to each request/response."""

    HEADER = "HTTP_X_REQUEST_ID"
    RESPONSE_HEADER = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(self.HEADER, "")
        if incoming and _VALID_ID_RE.match(incoming):
            request_id = incoming
        else:
            request_id = uuid.uuid4().hex

        request.request_id = request_id
        _set_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            _clear_request_id()

        # Best-effort echo; a few Django response types (e.g. streaming) may
        # not yet have headers populated — the attribute assignment still works.
        try:
            response[self.RESPONSE_HEADER] = request_id
        except Exception:  # pragma: no cover - defensive only
            pass
        return response


class RequestIDFilter(logging.Filter):
    """Logging filter that injects ``request_id`` onto every log record.

    Use in a ``LOGGING`` config via ``'filters': ['request_id']`` and reference
    ``%(request_id)s`` (or ``{request_id}`` with ``{`` style) in a formatter.
    Records produced outside a request context get ``'-'``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True
