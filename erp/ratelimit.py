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

        @ratelimit(group="login", rate="3/5m")   # 3 per 5 minutes
        def login_view(request): ...
    """
    num, period_spec = rate.split("/")
    max_requests = int(num)

    # Support compound periods like "5m" (5 minutes), "2h", etc.
    _period_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if period_spec[-1] in _period_map:
        unit_seconds = _period_map[period_spec[-1]]
        multiplier = int(period_spec[:-1]) if len(period_spec) > 1 else 1
        period_seconds = unit_seconds * multiplier
    else:
        raise ValueError(f"Unknown rate period: {period_spec!r}")

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


class HeavyOperationThrottle(SimpleRateThrottle):
    """Strict per-user limit for CPU/memory-intensive endpoints.

    Applied to on-demand AI trigger endpoints (lead scoring, ML training,
    anomaly detection, etc.) so a single user cannot flood the ML worker
    queue.  Rate is configurable via DEFAULT_THROTTLE_RATES['heavy'].
    Defaults to 10 per hour if not set.
    """
    scope = "heavy"

    def get_cache_key(self, request, view):
        # Key by authenticated user ID rather than IP so the limit is
        # per-account, not per-network egress point.
        if request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


# ---------------------------------------------------------------------------
# Account lockout — failed-login tracking
# ---------------------------------------------------------------------------

_LOCKOUT_MAX_FAILURES = 10       # lock after this many consecutive failures
_LOCKOUT_WINDOW_SECONDS = 900    # 15-minute sliding window
_LOCKOUT_DURATION_SECONDS = 1800 # 30-minute lockout


def _lockout_key(username):
    raw = f"ratelimit:lockout:{username}"
    return hashlib.md5(raw.encode()).hexdigest()


def record_failed_login(username):
    """Record one failed login attempt for *username*."""
    key = _lockout_key(username)
    now = time.time()
    history = cache.get(key, [])
    history = [t for t in history if t > now - _LOCKOUT_WINDOW_SECONDS]
    history.append(now)
    cache.set(key, history, _LOCKOUT_WINDOW_SECONDS + _LOCKOUT_DURATION_SECONDS)
    if len(history) >= _LOCKOUT_MAX_FAILURES:
        logger.warning("Account lockout triggered for user=%s (%d failures)",
                       username, len(history))


def check_account_lockout(username):
    """Return (is_locked, message) for *username*."""
    key = _lockout_key(username)
    now = time.time()
    history = cache.get(key, [])
    # Keep only entries inside the window
    history = [t for t in history if t > now - _LOCKOUT_WINDOW_SECONDS]
    if len(history) >= _LOCKOUT_MAX_FAILURES:
        # How long until the oldest failure falls out of the window?
        seconds_left = int(history[0] + _LOCKOUT_WINDOW_SECONDS - now) + 1
        minutes_left = max(seconds_left // 60, 1)
        return True, (
            f"Account temporarily locked due to too many failed login "
            f"attempts. Please try again in {minutes_left} minute(s)."
        )
    return False, ""


def clear_failed_logins(username):
    """Clear the lockout counter after a successful login."""
    cache.delete(_lockout_key(username))
