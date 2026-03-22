"""
Operational endpoints for infrastructure health checks.

/health/  — liveness probe (unauthenticated, JSON).
            Returns 200 {"status": "ok"} when the app and database are reachable.
            Returns 503 {"status": "error", "detail": "..."} otherwise.

Suitable for:
  - Docker Compose / Kubernetes liveness probes
  - Nginx upstream health checks  (proxy_next_upstream_tries)
  - Load-balancer health polling
  - CI smoke tests after deploy

Do NOT add authentication here — monitoring tools cannot supply session cookies.
"""

import time

from django.db import connection, OperationalError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def health_check(request):
    """Liveness probe: verify the web process and database are reachable."""
    t0 = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except OperationalError as exc:
        return JsonResponse(
            {'status': 'error', 'detail': f'database unreachable: {exc}'},
            status=503,
        )
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
    return JsonResponse({'status': 'ok', 'db_ms': elapsed_ms})
