"""
Platform Admin - Analytics & Reporting Views
"""

import csv
import json
from datetime import timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncMonth

from tenants.models import (
    TenantUser, PostgresServer, TenantDatabase,
    ServerLog,
)
from . import platform_admin_required, pa_context


@platform_admin_required
def pa_analytics(request):
    """Analytics dashboard with charts and trends."""
    now = timezone.now()
    period = request.GET.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30
    cutoff = now - timedelta(days=days)

    # ── User Growth ──
    user_growth = list(
        TenantUser.objects.filter(created_at__gte=cutoff, is_staff=False)
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    # ── Database Growth ──
    db_growth = list(
        TenantDatabase.objects.filter(created_at__gte=cutoff)
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    # ── Approval funnel ──
    total_signups = TenantUser.objects.filter(is_staff=False, created_at__gte=cutoff).count()
    total_approved = TenantUser.objects.filter(
        is_staff=False, approval_status='approved', approved_at__gte=cutoff
    ).count()
    total_rejected = TenantUser.objects.filter(
        is_staff=False, approval_status='rejected', created_at__gte=cutoff
    ).count()
    total_pending = TenantUser.objects.filter(
        is_staff=False, approval_status='pending', created_at__gte=cutoff
    ).count()

    # ── Server utilization ──
    server_utilization = list(
        PostgresServer.objects.annotate(
            db_count=Count('databases'),
            active_db_count=Count('databases', filter=Q(databases__status='active')),
        ).values('name', 'max_databases', 'db_count', 'active_db_count', 'status')
    )

    # ── Activity by action type ──
    activity_breakdown = list(
        ServerLog.objects.filter(created_at__gte=cutoff)
        .values('action')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # ── Error rate ──
    total_operations = ServerLog.objects.filter(created_at__gte=cutoff).count()
    error_operations = ServerLog.objects.filter(created_at__gte=cutoff, level='error').count()
    error_rate = (error_operations / total_operations * 100) if total_operations > 0 else 0

    # ── Top databases by user count ──
    top_databases = list(
        TenantDatabase.objects.filter(status='active')
        .annotate(user_count=Count('assignments', filter=Q(assignments__is_active=True)))
        .order_by('-user_count')[:10]
        .values('display_name', 'name', 'user_count')
    )

    # ── Monthly trends (last 12 months) ──
    twelve_months_ago = now - timedelta(days=365)
    monthly_users = list(
        TenantUser.objects.filter(created_at__gte=twelve_months_ago, is_staff=False)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    context = pa_context(request, {
        'period': days,
        # User growth
        'user_growth_labels': json.dumps([u['date'].strftime('%b %d') for u in user_growth]),
        'user_growth_data': json.dumps([u['count'] for u in user_growth]),
        # Database growth
        'db_growth_labels': json.dumps([d['date'].strftime('%b %d') for d in db_growth]),
        'db_growth_data': json.dumps([d['count'] for d in db_growth]),
        # Funnel
        'total_signups': total_signups,
        'total_approved': total_approved,
        'total_rejected': total_rejected,
        'total_pending': total_pending,
        'approval_rate': (total_approved / total_signups * 100) if total_signups > 0 else 0,
        # Server utilization
        'server_utilization': server_utilization,
        'server_names': json.dumps([s['name'] for s in server_utilization]),
        'server_usage': json.dumps([s['db_count'] for s in server_utilization]),
        'server_capacity': json.dumps([s['max_databases'] for s in server_utilization]),
        # Activity
        'activity_breakdown': activity_breakdown,
        'activity_labels': json.dumps([a['action'] for a in activity_breakdown]),
        'activity_data': json.dumps([a['count'] for a in activity_breakdown]),
        # Error rate
        'error_rate': round(error_rate, 1),
        'total_operations': total_operations,
        'error_operations': error_operations,
        # Top databases
        'top_databases': top_databases,
        # Monthly
        'monthly_labels': json.dumps([m['month'].strftime('%b %Y') for m in monthly_users]),
        'monthly_data': json.dumps([m['count'] for m in monthly_users]),
    })
    return render(request, 'platform_admin/analytics/dashboard.html', context)


@platform_admin_required
def pa_export_users(request):
    """Export users as CSV."""
    fmt = request.GET.get('format', 'csv')
    status_filter = request.GET.get('status')

    qs = TenantUser.objects.filter(is_staff=False).order_by('-created_at')
    if status_filter:
        qs = qs.filter(approval_status=status_filter)

    if fmt == 'json':
        data = list(qs.values(
            'email', 'first_name', 'last_name', 'company_name',
            'phone', 'approval_status', 'created_at', 'approved_at',
        ))
        for item in data:
            for k, v in item.items():
                if hasattr(v, 'isoformat'):
                    item[k] = v.isoformat()
        response = JsonResponse(data, safe=False)
        response['Content-Disposition'] = 'attachment; filename="users_export.json"'
        return response

    # Default: CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
    response.write('\ufeff')  # BOM for Excel UTF-8

    writer = csv.writer(response)
    writer.writerow(['Email', 'First Name', 'Last Name', 'Company', 'Phone', 'Status', 'Created', 'Approved'])

    for u in qs:
        writer.writerow([
            u.email, u.first_name, u.last_name, u.company_name,
            u.phone, u.approval_status,
            u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else '',
            u.approved_at.strftime('%Y-%m-%d %H:%M') if u.approved_at else '',
        ])

    return response


@platform_admin_required
def pa_export_databases(request):
    """Export databases as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="databases_export.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['Name', 'Display Name', 'Server', 'Status', 'Users', 'Created', 'Migrated'])

    qs = TenantDatabase.objects.select_related('server').annotate(
        user_count=Count('assignments', filter=Q(assignments__is_active=True))
    ).order_by('-created_at')

    for db in qs:
        writer.writerow([
            db.name, db.display_name, db.server.name, db.status,
            db.user_count,
            db.created_at.strftime('%Y-%m-%d %H:%M') if db.created_at else '',
            'Yes' if db.is_migrated else 'No',
        ])
    return response


@platform_admin_required
def pa_export_logs(request):
    """Export system logs as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="system_logs_export.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Level', 'Action', 'Server', 'Database', 'User', 'Message'])

    qs = ServerLog.objects.select_related('server', 'database', 'user').order_by('-created_at')[:5000]

    for log in qs:
        writer.writerow([
            log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            log.level, log.get_action_display(),
            log.server.name if log.server else '',
            log.database.name if log.database else '',
            log.user.email if log.user else '',
            log.message,
        ])
    return response
