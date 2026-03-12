"""
Rate-limiting utilities.

Provides:
  - A Django view decorator for form-based views (login, signup).
  - Custom DRF throttle classes for API endpoints.

Uses Django's cache framework (backed by Redis when available).
"""

import hashlib
import logging
import time

from django.core.cache import cache
from django.http import HttpResponse
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request):
    """Return the real client IP, respecting X-Forwarded-For behind a proxy."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # Take the first (client) address only
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _cache_key(group, ident):
    raw = f"ratelimit:{group}:{ident}"
    return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# View decorator – for login / signup (non-DRF views)
# ---------------------------------------------------------------------------

def ratelimit(*, group, rate, method="POST", block=True):
    """
    Decorator that rate-limits a Django view by client IP.

    Parameters
    ----------
    group : str   – logical name, e.g. "login" or "signup"
    rate  : str   – "<num_requests>/<period>", period one of s/m/h/d
    method: str   – HTTP method to limit ("POST", "GET", or "ALL")
    block : bool  – if True, return 429; otherwise just annotate request

    Example::

        @ratelimit(group="login", rate="5/m")
        def login_view(request): ...
    """
    num, period_char = rate.split("/")
    max_requests = int(num)
    period_seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[period_char]

    def decorator(view_func):
        from functools import wraps

        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if method != "ALL" and request.method != method:
                return view_func(request, *args, **kwargs)

            ip = _get_client_ip(request)
            key = _cache_key(group, ip)
            now = time.time()

            # Sliding-window log stored as list of timestamps
            history = cache.get(key, [])
            # Discard entries outside the window
            history = [t for t in history if t > now - period_seconds]

            if len(history) >= max_requests:
                logger.warning(
                    "Rate limit exceeded: group=%s ip=%s (%d/%ds)",
                    group, ip, max_requests, period_seconds,
                )
                if block:
                    retry_after = int(history[0] - (now - period_seconds)) + 1
                    resp = HttpResponse(
                        "Too many requests. Please try again later.",
                        status=429,
                        content_type="text/plain",
                    )
                    resp["Retry-After"] = str(max(retry_after, 1))
                    return resp

            history.append(now)
            cache.set(key, history, period_seconds)

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


# ---------------------------------------------------------------------------
# DRF throttle classes – for REST API endpoints
# ---------------------------------------------------------------------------

class BurstRateThrottle(SimpleRateThrottle):
    """Short burst limit per IP (e.g. 60/min)."""
    scope = "burst"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class SustainedRateThrottle(SimpleRateThrottle):
    """Sustained daily limit per IP (e.g. 1000/day)."""
    scope = "sustained"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginRateThrottle(SimpleRateThrottle):
    """Strict limit for any DRF token-auth / login API endpoints."""
    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
