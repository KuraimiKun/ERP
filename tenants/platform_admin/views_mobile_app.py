"""
Platform Admin - Mobile App (Flutter) Build Management

Provides a page for superusers to trigger a release build of the
Flutter mobile app and replace the APK served from the downloads folder
(``static/downloads/intara-erp-employee.apk``).

The build runs in a background thread. Its status is stored in the
Django cache so the page can reflect progress across requests.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from . import pa_context, platform_admin_required


# ── Constants ────────────────────────────────────────────────────────────────

BUILD_STATUS_CACHE_KEY = "platform_admin:flutter_build:status"
BUILD_LOCK_CACHE_KEY = "platform_admin:flutter_build:lock"
BUILD_LOG_MAX_CHARS = 20000
# Cache entries should outlive a typical build but eventually expire.
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

MOBILE_APP_DIR = Path(settings.BASE_DIR) / "mobile"
APK_OUTPUT_RELATIVE = Path("build") / "app" / "outputs" / "flutter-apk" / "app-release.apk"
DOWNLOADS_DIR = Path(settings.BASE_DIR) / "static" / "downloads"
DOWNLOADS_APK_NAME = "intara-erp-employee.apk"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_status() -> dict:
    return cache.get(BUILD_STATUS_CACHE_KEY) or {"status": "idle"}


def _set_status(data: dict) -> None:
    cache.set(BUILD_STATUS_CACHE_KEY, data, CACHE_TTL_SECONDS)


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"


def _current_apk_info() -> dict:
    apk_path = DOWNLOADS_DIR / DOWNLOADS_APK_NAME
    if not apk_path.exists():
        return {"exists": False, "path": str(apk_path)}
    stat = apk_path.stat()
    return {
        "exists": True,
        "path": str(apk_path),
        "size": _format_size(stat.st_size),
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def _find_flutter_executable() -> str | None:
    """Locate the ``flutter`` executable, falling back to a configured path."""
    configured = getattr(settings, "FLUTTER_EXECUTABLE", None) or os.environ.get("FLUTTER_EXECUTABLE")
    if configured and Path(configured).exists():
        return configured
    return shutil.which("flutter")


# ── Build Worker ─────────────────────────────────────────────────────────────


def _run_flutter_build(triggered_by: str) -> None:
    """Run ``flutter build apk --release`` and copy the APK to downloads.

    Executed in a background thread. Progress and result are written to the
    cache under ``BUILD_STATUS_CACHE_KEY``.
    """
    status: dict = {
        "status": "running",
        "started_at": _now_iso(),
        "finished_at": None,
        "triggered_by": triggered_by,
        "log": "",
        "error": None,
        "apk": None,
    }
    _set_status(status)

    try:
        flutter = _find_flutter_executable()
        if not flutter:
            raise RuntimeError(
                "The 'flutter' executable was not found on PATH. "
                "Install the Flutter SDK on the server or set the "
                "FLUTTER_EXECUTABLE setting / environment variable."
            )

        if not MOBILE_APP_DIR.exists():
            raise RuntimeError(f"Mobile project directory not found: {MOBILE_APP_DIR}")

        log_parts: list[str] = [
            f"$ cd {MOBILE_APP_DIR}",
            f"$ {flutter} build apk --release",
            "",
        ]
        _set_status({**status, "log": "\n".join(log_parts)})

        proc = subprocess.run(  # noqa: S603 - trusted args, no user input
            [flutter, "build", "apk", "--release"],
            cwd=str(MOBILE_APP_DIR),
            capture_output=True,
            text=True,
            timeout=60 * 60,  # 1 hour safety timeout
            check=False,
        )

        log_parts.append(proc.stdout or "")
        if proc.stderr:
            log_parts.append("\n[stderr]\n" + proc.stderr)
        combined_log = "\n".join(log_parts)[-BUILD_LOG_MAX_CHARS:]

        if proc.returncode != 0:
            status.update(
                {
                    "status": "error",
                    "finished_at": _now_iso(),
                    "log": combined_log,
                    "error": f"flutter build exited with code {proc.returncode}",
                }
            )
            _set_status(status)
            return

        apk_src = MOBILE_APP_DIR / APK_OUTPUT_RELATIVE
        if not apk_src.exists():
            status.update(
                {
                    "status": "error",
                    "finished_at": _now_iso(),
                    "log": combined_log,
                    "error": f"Build finished but APK not found at {apk_src}",
                }
            )
            _set_status(status)
            return

        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        apk_dst = DOWNLOADS_DIR / DOWNLOADS_APK_NAME
        shutil.copyfile(apk_src, apk_dst)

        status.update(
            {
                "status": "success",
                "finished_at": _now_iso(),
                "log": combined_log,
                "error": None,
                "apk": {
                    "path": str(apk_dst),
                    "size": _format_size(apk_dst.stat().st_size),
                },
            }
        )
        _set_status(status)
    except subprocess.TimeoutExpired:
        status.update(
            {
                "status": "error",
                "finished_at": _now_iso(),
                "error": "Build timed out after 1 hour.",
            }
        )
        _set_status(status)
    except Exception as exc:  # noqa: BLE001 - surface any error to the UI
        status.update(
            {
                "status": "error",
                "finished_at": _now_iso(),
                "error": str(exc),
            }
        )
        _set_status(status)
    finally:
        cache.delete(BUILD_LOCK_CACHE_KEY)


# ── Views ────────────────────────────────────────────────────────────────────


@platform_admin_required
def pa_mobile_app(request):
    """Mobile app management page (status + build trigger)."""
    status = _get_status()
    context = pa_context(
        request,
        {
            "build_status": status,
            "apk_info": _current_apk_info(),
            "mobile_dir": str(MOBILE_APP_DIR),
            "downloads_dir": str(DOWNLOADS_DIR),
            "flutter_executable": _find_flutter_executable(),
            "is_building": status.get("status") == "running",
        },
    )
    return render(request, "platform_admin/mobile_app.html", context)


@platform_admin_required
@require_POST
def pa_mobile_app_build(request):
    """Trigger a Flutter release build in a background thread."""
    # Prevent concurrent builds using a short-lived cache lock.
    if not cache.add(BUILD_LOCK_CACHE_KEY, True, CACHE_TTL_SECONDS):
        messages.warning(request, _("A build is already running. Please wait for it to finish."))
        return redirect("tenants:pa_mobile_app")

    current = _get_status()
    if current.get("status") == "running":
        messages.warning(request, _("A build is already running. Please wait for it to finish."))
        return redirect("tenants:pa_mobile_app")

    triggered_by = request.user.get_username() if request.user.is_authenticated else "unknown"
    thread = threading.Thread(
        target=_run_flutter_build,
        args=(triggered_by,),
        name="flutter-build-worker",
        daemon=True,
    )
    thread.start()

    messages.success(
        request,
        _("Flutter build started. This can take several minutes; refresh this page to see progress."),
    )
    return redirect("tenants:pa_mobile_app")
