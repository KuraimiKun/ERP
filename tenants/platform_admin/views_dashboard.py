"""
Platform Admin - Dashboard Views
"""

from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncMonth
from datetime import timedelta
import json

from tenants.models import (
    TenantUser, PostgresServer, TenantDatabase,
    DatabaseAssignment, ServerLog,
)
from . import platform_admin_required, pa_context


@platform_admin_required
def pa_dashboard(request):
    """Platform admin dashboard with system-wide stats."""
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # ── User stats ──
    total_users = TenantUser.objects.filter(is_staff=False).count()
    pending_users = TenantUser.objects.filter(approval_status='pending', is_staff=False).count()
    approved_users = TenantUser.objects.filter(approval_status='approved', is_staff=False).count()
    suspended_users = TenantUser.objects.filter(approval_status='suspended', is_staff=False).count()
    rejected_users = TenantUser.objects.filter(approval_status='rejected', is_staff=False).count()
    new_users_30d = TenantUser.objects.filter(
        created_at__gte=thirty_days_ago, is_staff=False
    ).count()
    new_users_7d = TenantUser.objects.filter(
        created_at__gte=seven_days_ago, is_staff=False
    ).count()

    # ── Server stats ──
    total_servers = PostgresServer.objects.count()
    active_servers = PostgresServer.objects.filter(status='active').count()

    # ── Database stats ──
    total_databases = TenantDatabase.objects.count()
    active_databases = TenantDatabase.objects.filter(status='active').count()

    # ── Assignment stats ──
    total_assignments = DatabaseAssignment.objects.filter(is_active=True).count()

    # ── Charts: user signups last 30 days ──
    signups_chart = list(
        TenantUser.objects.filter(
            created_at__gte=thirty_days_ago, is_staff=False,
        )
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    signups_labels = [s['date'].strftime('%b %d') for s in signups_chart]
    signups_data = [s['count'] for s in signups_chart]

    # ── Charts: databases created last 6 months ──
    six_months_ago = now - timedelta(days=180)
    db_chart = list(
        TenantDatabase.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    db_labels = [d['month'].strftime('%b %Y') for d in db_chart]
    db_data = [d['count'] for d in db_chart]

    # ── Recent activity ──
    recent_logs = ServerLog.objects.select_related('server', 'database', 'user')[:10]
    recent_users = TenantUser.objects.filter(is_staff=False).order_by('-created_at')[:8]
    pending_list = TenantUser.objects.filter(
        approval_status='pending', is_staff=False
    ).order_by('-created_at')[:5]

    # ── Server capacity ──
    servers_with_capacity = PostgresServer.objects.annotate(
        db_count=Count('databases')
    ).filter(status='active')

    context = pa_context(request, {
        'total_users': total_users,
        'pending_users': pending_users,
        'approved_users': approved_users,
        'suspended_users': suspended_users,
        'rejected_users': rejected_users,
        'new_users_30d': new_users_30d,
        'new_users_7d': new_users_7d,
        'total_servers': total_servers,
        'active_servers': active_servers,
        'total_databases': total_databases,
        'active_databases': active_databases,
        'total_assignments': total_assignments,
        'signups_labels': json.dumps(signups_labels),
        'signups_data': json.dumps(signups_data),
        'db_labels': json.dumps(db_labels),
        'db_data': json.dumps(db_data),
        'recent_logs': recent_logs,
        'recent_users': recent_users,
        'pending_list': pending_list,
        'servers_with_capacity': servers_with_capacity,
    })
    return render(request, 'platform_admin/dashboard.html', context)
