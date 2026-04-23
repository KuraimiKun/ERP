"""
Platform Admin - Settings Views
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
import os

from . import platform_admin_required, pa_context


@platform_admin_required
def pa_settings(request):
    """Platform settings overview."""
    from django.conf import settings as django_settings

    # Compute disk usage for media/static
    media_size = _get_dir_size(django_settings.MEDIA_ROOT) if hasattr(django_settings, "MEDIA_ROOT") else 0
    static_size = (
        _get_dir_size(django_settings.STATIC_ROOT)
        if hasattr(django_settings, "STATIC_ROOT") and django_settings.STATIC_ROOT
        else 0
    )

    context = pa_context(
        request,
        {
            "debug": django_settings.DEBUG,
            "database_engine": django_settings.DATABASES.get("default", {}).get("ENGINE", ""),
            "database_name": django_settings.DATABASES.get("default", {}).get("NAME", ""),
            "installed_apps": django_settings.INSTALLED_APPS,
            "middleware": django_settings.MIDDLEWARE,
            "language_code": django_settings.LANGUAGE_CODE,
            "time_zone": django_settings.TIME_ZONE,
            "static_url": django_settings.STATIC_URL,
            "media_url": django_settings.MEDIA_URL,
            "allowed_hosts": django_settings.ALLOWED_HOSTS,
            "auth_user_model": django_settings.AUTH_USER_MODEL,
            "total_dynamic_dbs": len(django_settings.DATABASES) - 1,
            "email_backend": getattr(django_settings, "EMAIL_BACKEND", "Not configured"),
            "cache_backend": _get_cache_backend(django_settings),
            "session_engine": getattr(django_settings, "SESSION_ENGINE", "Default"),
            "media_size": _format_size(media_size),
            "static_size": _format_size(static_size),
            "python_version": _get_python_version(),
            "django_version": _get_django_version(),
        },
    )
    return render(request, "platform_admin/settings.html", context)


@platform_admin_required
@require_POST
def pa_clear_cache(request):
    """Clear Django cache."""
    try:
        from django.core.cache import cache

        cache.clear()
        messages.success(request, _("Cache cleared successfully."))
    except Exception as e:
        messages.error(request, _(f"Failed to clear cache: {e}"))
    return redirect("tenants:pa_settings")


@platform_admin_required
@require_POST
def pa_collect_static(request):
    """Run collectstatic management command."""
    try:
        from django.core.management import call_command

        call_command("collectstatic", "--noinput")
        messages.success(request, _("Static files collected successfully."))
    except Exception as e:
        messages.error(request, _(f"Failed to collect static files: {e}"))
    return redirect("tenants:pa_settings")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_dir_size(path):
    """Get total size of a directory in bytes."""
    total = 0
    if path and os.path.exists(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return total


def _format_size(size_bytes):
    """Format bytes into human-readable string."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"


def _get_cache_backend(settings):
    """Get cache backend name."""
    caches = getattr(settings, "CACHES", {})
    default = caches.get("default", {})
    backend = default.get("BACKEND", "Not configured")
    return backend.split(".")[-1] if "." in backend else backend


def _get_python_version():
    import sys

    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _get_django_version():
    import django

    return django.get_version()
