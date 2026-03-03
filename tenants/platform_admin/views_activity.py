"""
Platform Admin - Activity Feed Views
"""

from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from tenants.models import (
    TenantUser, DatabaseAssignment, ServerLog,
)
from . import platform_admin_required, pa_context


@platform_admin_required
def pa_activity(request):
    """Activity feed showing recent actions across the platform."""
    now = timezone.now()
    days = int(request.GET.get('days', 30))
    cutoff = now - timedelta(days=days)

    recent_signups = TenantUser.objects.filter(
        created_at__gte=cutoff, is_staff=False
    ).order_by('-created_at')[:20]

    recent_approvals = TenantUser.objects.filter(
        approved_at__gte=cutoff,
        approval_status='approved',
    ).order_by('-approved_at')[:20]

    recent_assignments = DatabaseAssignment.objects.filter(
        assigned_at__gte=cutoff
    ).select_related('user', 'database').order_by('-assigned_at')[:20]

    recent_logs = ServerLog.objects.select_related(
        'server', 'database', 'user'
    ).order_by('-created_at')[:30]

    context = pa_context(request, {
        'recent_signups': recent_signups,
        'recent_approvals': recent_approvals,
        'recent_assignments': recent_assignments,
        'recent_logs': recent_logs,
        'selected_days': days,
    })
    return render(request, 'platform_admin/activity.html', context)
