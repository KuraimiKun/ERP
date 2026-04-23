"""
Platform Admin - System Logs Views
"""

from django.shortcuts import render
from django.db.models import Q

from tenants.models import ServerLog
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_logs(request):
    """View system logs with filtering."""
    qs = ServerLog.objects.select_related("server", "database", "user").order_by("-created_at")

    level = request.GET.get("level")
    if level in ("info", "warning", "error", "success"):
        qs = qs.filter(level=level)

    action = request.GET.get("action")
    if action:
        qs = qs.filter(action=action)

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(message__icontains=search) | Q(server__name__icontains=search) | Q(database__name__icontains=search)
        )

    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    page = paginate(request, qs, per_page=50)

    context = pa_context(
        request,
        {
            "logs": page,
            "current_level": level,
            "current_action": action,
            "search_query": search,
            "date_from": date_from or "",
            "date_to": date_to or "",
            "action_choices": ServerLog.ACTION_CHOICES,
            "total_logs": ServerLog.objects.count(),
            "error_count": ServerLog.objects.filter(level="error").count(),
            "warning_count": ServerLog.objects.filter(level="warning").count(),
        },
    )
    return render(request, "platform_admin/logs/list.html", context)
