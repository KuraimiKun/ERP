"""
Platform Admin - Tenant Quotas & Usage Tracking Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json

from tenants.models import (
    TenantDatabase, TenantQuota, UsageSnapshot,
)
from .forms import TenantQuotaForm
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_quota_list(request):
    """List all tenant quotas with usage overview."""
    databases = TenantDatabase.objects.filter(status='active').select_related(
        'server', 'quota',
    ).order_by('display_name', 'name')

    # Create missing quotas
    for db in databases:
        if not hasattr(db, 'quota') or db.quota is None:
            TenantQuota.objects.get_or_create(database=db)

    # Re-fetch with quotas
    databases = TenantDatabase.objects.filter(status='active').select_related(
        'server', 'quota',
    ).order_by('display_name', 'name')

    # Filter
    warning_only = request.GET.get('warning') == '1'
    over_limit = request.GET.get('over') == '1'
    filtered_dbs = []
    for db in databases:
        q = db.quota
        if warning_only and q and not q.is_warning():
            continue
        if over_limit and q and not q.is_over_limit():
            continue
        filtered_dbs.append(db)

    page_obj = paginate(request, filtered_dbs, 20)

    context = pa_context(request, {
        'databases': page_obj,
        'warning_only': warning_only,
        'over_limit': over_limit,
        'total_databases': databases.count(),
    })
    return render(request, 'platform_admin/quotas/list.html', context)


@platform_admin_required
def pa_quota_edit(request, pk):
    """Edit quota limits for a tenant database."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    quota, _ = TenantQuota.objects.get_or_create(database=db)

    if request.method == 'POST':
        form = TenantQuotaForm(request.POST, instance=quota)
        if form.is_valid():
            form.save()
            messages.success(request, _(f'Quotas updated for {db.display_name or db.name}.'))
            return redirect('tenants:pa_quota_list')
    else:
        form = TenantQuotaForm(instance=quota)

    context = pa_context(request, {'form': form, 'database': db, 'quota': quota})
    return render(request, 'platform_admin/quotas/edit.html', context)


@platform_admin_required
def pa_quota_detail(request, pk):
    """Detailed usage view with historical chart for a database."""
    db = get_object_or_404(TenantDatabase.objects.select_related('server'), pk=pk)
    quota, _ = TenantQuota.objects.get_or_create(database=db)

    # Usage history (last 30 days)
    snapshots = UsageSnapshot.objects.filter(database=db).order_by('recorded_at')[:720]

    chart_labels = [s.recorded_at.strftime('%m/%d %H:%M') for s in snapshots]
    chart_size = [round(s.db_size_mb, 2) for s in snapshots]
    chart_conn = [s.connections for s in snapshots]
    chart_cache = [round(s.cache_hit_ratio, 2) for s in snapshots]

    # Refresh usage from live data
    try:
        from tenants.services.database_service import DatabaseService
        svc = DatabaseService(db.server)
        size_info = svc.get_database_size(db.name)
        conn_info = svc.get_active_connections(db.name)
        quota.current_db_size_mb = size_info.get('size_mb', 0)
        quota.current_connections = conn_info.get('count', 0)
        quota.last_checked = timezone.now()
        quota.save(update_fields=['current_db_size_mb', 'current_connections', 'last_checked'])
    except Exception:
        pass

    context = pa_context(request, {
        'database': db,
        'quota': quota,
        'chart_labels': json.dumps(chart_labels),
        'chart_size': json.dumps(chart_size),
        'chart_conn': json.dumps(chart_conn),
        'chart_cache': json.dumps(chart_cache),
        'snapshots': snapshots[:20],
    })
    return render(request, 'platform_admin/quotas/detail.html', context)


@platform_admin_required
@require_POST
def pa_quota_refresh(request, pk):
    """Refresh a single database's quota usage from live data."""
    db = get_object_or_404(TenantDatabase.objects.select_related('server'), pk=pk)
    quota, _ = TenantQuota.objects.get_or_create(database=db)

    try:
        from tenants.services.database_service import DatabaseService
        svc = DatabaseService(db.server)
        size_info = svc.get_database_size(db.name)
        conn_info = svc.get_active_connections(db.name)
        table_info = svc.get_table_stats(db.name)

        quota.current_db_size_mb = size_info.get('size_mb', 0)
        quota.current_connections = conn_info.get('count', 0)
        quota.current_tables = len(table_info) if isinstance(table_info, list) else 0
        quota.last_checked = timezone.now()
        quota.save()

        messages.success(request, _('Usage data refreshed.'))
    except Exception as e:
        messages.error(request, _(f'Failed to refresh usage: {e}'))

    return redirect('tenants:pa_quota_detail', pk=pk)


@platform_admin_required
def pa_quota_api(request, pk):
    """JSON endpoint for live quota data (for AJAX refresh)."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    quota, _ = TenantQuota.objects.get_or_create(database=db)

    return JsonResponse({
        'size_pct': quota.size_usage_pct(),
        'conn_pct': quota.connection_usage_pct(),
        'current_size_mb': quota.current_db_size_mb,
        'current_connections': quota.current_connections,
        'current_tables': quota.current_tables,
        'is_warning': quota.is_warning(),
        'is_over': quota.is_over_limit(),
    })
