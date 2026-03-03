"""
Platform Admin - Monitoring History & Charts Views
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Avg
from datetime import timedelta
import json

from tenants.models import PostgresServer, MetricSnapshot, TenantDatabase, UsageSnapshot
from . import platform_admin_required, pa_context


@platform_admin_required
def pa_monitoring(request):
    """Monitoring dashboard with historical charts for all servers."""
    servers = PostgresServer.objects.filter(status='active').order_by('name')
    selected_pk = request.GET.get('server')
    hours = int(request.GET.get('hours', 24))

    if selected_pk:
        try:
            selected_server = PostgresServer.objects.get(pk=selected_pk)
        except PostgresServer.DoesNotExist:
            selected_server = servers.first()
    else:
        selected_server = servers.first()

    chart_data = {}
    if selected_server:
        since = timezone.now() - timedelta(hours=hours)
        snapshots = MetricSnapshot.objects.filter(
            server=selected_server,
            recorded_at__gte=since,
        ).order_by('recorded_at')

        chart_data = {
            'labels': [s.recorded_at.strftime('%H:%M') for s in snapshots],
            'cpu': [round(s.cpu_percent, 1) for s in snapshots],
            'memory': [round(s.memory_percent, 1) for s in snapshots],
            'connections': [s.total_connections for s in snapshots],
            'active_connections': [s.active_connections for s in snapshots],
            'db_size': [round(s.total_db_size_mb, 1) for s in snapshots],
            'cache_hit': [round(s.cache_hit_ratio, 2) for s in snapshots],
            'net_rx': [round(s.net_rx_mb, 2) for s in snapshots],
            'net_tx': [round(s.net_tx_mb, 2) for s in snapshots],
            'tps': [round(s.transactions_per_sec, 1) for s in snapshots],
        }

    # Latest values for status cards
    latest = None
    if selected_server:
        latest = MetricSnapshot.objects.filter(server=selected_server).order_by('-recorded_at').first()

    # Server comparison (average metrics over last 24h)
    comparison = []
    since_24h = timezone.now() - timedelta(hours=24)
    for srv in servers:
        avg = MetricSnapshot.objects.filter(
            server=srv, recorded_at__gte=since_24h,
        ).aggregate(
            avg_cpu=Avg('cpu_percent'),
            avg_mem=Avg('memory_percent'),
            avg_conn=Avg('total_connections'),
            avg_cache=Avg('cache_hit_ratio'),
        )
        comparison.append({
            'server': srv,
            'avg_cpu': round(avg['avg_cpu'] or 0, 1),
            'avg_mem': round(avg['avg_mem'] or 0, 1),
            'avg_conn': round(avg['avg_conn'] or 0),
            'avg_cache': round(avg['avg_cache'] or 0, 2),
        })

    context = pa_context(request, {
        'servers': servers,
        'selected_server': selected_server,
        'chart_data': json.dumps(chart_data),
        'latest': latest,
        'comparison': comparison,
        'hours': hours,
    })
    return render(request, 'platform_admin/monitoring/dashboard.html', context)


@platform_admin_required
def pa_monitoring_server(request, pk):
    """Detailed monitoring for a specific server."""
    server = get_object_or_404(PostgresServer, pk=pk)
    hours = int(request.GET.get('hours', 24))
    since = timezone.now() - timedelta(hours=hours)

    snapshots = MetricSnapshot.objects.filter(
        server=server, recorded_at__gte=since,
    ).order_by('recorded_at')

    chart_data = {
        'labels': [s.recorded_at.strftime('%m/%d %H:%M') for s in snapshots],
        'cpu': [round(s.cpu_percent, 1) for s in snapshots],
        'memory': [round(s.memory_percent, 1) for s in snapshots],
        'memory_used_mb': [round(s.memory_used_mb, 1) for s in snapshots],
        'disk_used_mb': [round(s.disk_used_mb, 1) for s in snapshots],
        'connections': [s.total_connections for s in snapshots],
        'active': [s.active_connections for s in snapshots],
        'cache': [round(s.cache_hit_ratio, 2) for s in snapshots],
        'tps': [round(s.transactions_per_sec, 1) for s in snapshots],
        'net_rx': [round(s.net_rx_mb, 2) for s in snapshots],
        'net_tx': [round(s.net_tx_mb, 2) for s in snapshots],
    }

    latest = snapshots.last()

    # Database-level usage snapshots
    databases = TenantDatabase.objects.filter(server=server, status='active')
    db_usage = []
    for db in databases:
        last_snap = UsageSnapshot.objects.filter(database=db).order_by('-recorded_at').first()
        db_usage.append({
            'database': db,
            'snapshot': last_snap,
        })

    context = pa_context(request, {
        'server': server,
        'chart_data': json.dumps(chart_data),
        'latest': latest,
        'hours': hours,
        'db_usage': db_usage,
        'snapshot_count': snapshots.count(),
    })
    return render(request, 'platform_admin/monitoring/server.html', context)


@platform_admin_required
def pa_monitoring_api(request, pk):
    """JSON endpoint for real-time chart updates."""
    server = get_object_or_404(PostgresServer, pk=pk)
    hours = int(request.GET.get('hours', 1))
    since = timezone.now() - timedelta(hours=hours)

    snapshots = MetricSnapshot.objects.filter(
        server=server, recorded_at__gte=since,
    ).order_by('recorded_at')

    data = {
        'labels': [s.recorded_at.strftime('%H:%M') for s in snapshots],
        'cpu': [round(s.cpu_percent, 1) for s in snapshots],
        'memory': [round(s.memory_percent, 1) for s in snapshots],
        'connections': [s.total_connections for s in snapshots],
        'cache': [round(s.cache_hit_ratio, 2) for s in snapshots],
    }
    return JsonResponse(data)
