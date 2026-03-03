"""
Platform Admin - System Health Overview Views
"""

from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q, Avg
from django.views.decorators.http import require_POST
from datetime import timedelta
import os

from tenants.models import (
    PostgresServer, TenantDatabase, ServerLog, TenantUser,
    DatabaseAssignment,
)
from . import platform_admin_required, pa_context


@platform_admin_required
def pa_health(request):
    """System health overview - aggregated status of all components."""
    now = timezone.now()
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(days=1)

    # ── Server Health ──
    servers = PostgresServer.objects.annotate(
        db_count=Count('databases'),
        active_db_count=Count('databases', filter=Q(databases__status='active')),
    ).order_by('name')

    total_servers = servers.count()
    healthy_servers = servers.filter(status='active').count()
    unhealthy_servers = servers.filter(status__in=['error', 'inactive']).count()
    maintenance_servers = servers.filter(status='maintenance').count()

    # ── Database Health ──
    total_databases = TenantDatabase.objects.count()
    active_databases = TenantDatabase.objects.filter(status='active').count()
    error_databases = TenantDatabase.objects.filter(status='error').count()
    unmigrated_databases = TenantDatabase.objects.filter(
        status='active', is_migrated=False
    ).count()

    # ── Recent Errors ──
    recent_errors = ServerLog.objects.filter(
        level='error', created_at__gte=one_day_ago
    ).select_related('server', 'database').order_by('-created_at')[:20]

    errors_last_hour = ServerLog.objects.filter(
        level='error', created_at__gte=one_hour_ago
    ).count()
    errors_last_day = ServerLog.objects.filter(
        level='error', created_at__gte=one_day_ago
    ).count()

    # ── User Health ──
    total_users = TenantUser.objects.filter(is_staff=False).count()
    users_without_db = TenantUser.objects.filter(
        is_staff=False, approval_status='approved'
    ).exclude(database_assignments__is_active=True).count()
    stale_pending = TenantUser.objects.filter(
        is_staff=False, approval_status='pending',
        created_at__lt=now - timedelta(days=7)
    ).count()

    # ── Stale health checks ──
    stale_health_checks = PostgresServer.objects.filter(
        Q(last_health_check__isnull=True) |
        Q(last_health_check__lt=now - timedelta(hours=24)),
        status='active',
    ).count()

    # ── Overall score ──
    issues = []
    if unhealthy_servers > 0:
        issues.append({'severity': 'error', 'message': f'{unhealthy_servers} server(s) unhealthy'})
    if error_databases > 0:
        issues.append({'severity': 'error', 'message': f'{error_databases} database(s) in error state'})
    if unmigrated_databases > 0:
        issues.append({'severity': 'warning', 'message': f'{unmigrated_databases} database(s) not migrated'})
    if users_without_db > 0:
        issues.append({'severity': 'warning', 'message': f'{users_without_db} approved user(s) without database'})
    if stale_pending > 0:
        issues.append({'severity': 'info', 'message': f'{stale_pending} user(s) pending for 7+ days'})
    if stale_health_checks > 0:
        issues.append({'severity': 'warning', 'message': f'{stale_health_checks} server(s) with stale health checks'})
    if errors_last_hour > 5:
        issues.append({'severity': 'error', 'message': f'{errors_last_hour} errors in the last hour'})

    error_issues = sum(1 for i in issues if i['severity'] == 'error')
    warning_issues = sum(1 for i in issues if i['severity'] == 'warning')

    if error_issues > 0:
        health_status = 'critical'
        health_score = max(0, 100 - (error_issues * 20) - (warning_issues * 5))
    elif warning_issues > 0:
        health_status = 'warning'
        health_score = max(50, 100 - (warning_issues * 10))
    else:
        health_status = 'healthy'
        health_score = 100

    # ── Disk usage (basic) ──
    try:
        disk = os.statvfs('/') if os.name != 'nt' else None
        if disk:
            disk_total = disk.f_blocks * disk.f_frsize
            disk_free = disk.f_bfree * disk.f_frsize
            disk_used_pct = round((1 - disk_free / disk_total) * 100, 1)
        else:
            import shutil
            total, used, free = shutil.disk_usage('/')
            disk_total = total
            disk_free = free
            disk_used_pct = round(used / total * 100, 1)
    except Exception:
        disk_total = 0
        disk_free = 0
        disk_used_pct = 0

    context = pa_context(request, {
        # Servers
        'servers': servers,
        'total_servers': total_servers,
        'healthy_servers': healthy_servers,
        'unhealthy_servers': unhealthy_servers,
        'maintenance_servers': maintenance_servers,
        # Databases
        'total_databases': total_databases,
        'active_databases': active_databases,
        'error_databases': error_databases,
        'unmigrated_databases': unmigrated_databases,
        # Errors
        'recent_errors': recent_errors,
        'errors_last_hour': errors_last_hour,
        'errors_last_day': errors_last_day,
        # Users
        'total_users': total_users,
        'users_without_db': users_without_db,
        'stale_pending': stale_pending,
        # Health
        'issues': issues,
        'health_status': health_status,
        'health_score': health_score,
        # Disk
        'disk_used_pct': disk_used_pct,
    })
    return render(request, 'platform_admin/health/overview.html', context)
