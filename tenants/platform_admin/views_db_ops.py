"""
Platform Admin - Database Operations (Enterprise) Views

Database performance analytics, table browser, active connections,
maintenance operations, export/import, clone, password reset, locks.
"""

import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.conf import settings

from tenants.models import TenantDatabase, ServerLog
from tenants.services.database_service import DatabaseService
from . import platform_admin_required, pa_context


# ── Performance Dashboard ────────────────────────────────────────────────────

@platform_admin_required
def pa_db_performance(request, pk):
    """Database performance analytics dashboard."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    perf = svc.get_database_performance(db)
    size = svc.get_database_size(db)
    long_queries = svc.get_long_running_queries(db, min_seconds=5)

    context = pa_context(request, {
        'database': db,
        'performance': perf,
        'size': size,
        'long_queries': long_queries,
    })
    return render(request, 'platform_admin/db_ops/performance.html', context)


# ── Table Browser ────────────────────────────────────────────────────────────

@platform_admin_required
def pa_db_tables(request, pk):
    """Table-level stats: row counts, sizes, dead tuples, last vacuum."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    tables = svc.get_table_stats(db)
    indexes = svc.get_index_stats(db)

    context = pa_context(request, {
        'database': db,
        'tables': tables,
        'indexes': indexes,
    })
    return render(request, 'platform_admin/db_ops/tables.html', context)


# ── Active Connections ───────────────────────────────────────────────────────

@platform_admin_required
def pa_db_connections(request, pk):
    """View and manage active database connections."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    connections = svc.get_active_connections(db)

    context = pa_context(request, {
        'database': db,
        'connections': connections,
    })
    return render(request, 'platform_admin/db_ops/connections.html', context)


@platform_admin_required
def pa_db_connections_api(request, pk):
    """AJAX endpoint returning current connections as JSON."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()
    connections = svc.get_active_connections(db)
    return JsonResponse({'connections': connections})


@platform_admin_required
@require_POST
def pa_db_kill_connection(request, pk):
    """Terminate a specific database connection."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    pid = request.POST.get('pid')
    if not pid:
        messages.error(request, _('No PID specified.'))
        return redirect('tenants:pa_db_connections', pk=pk)

    try:
        result = svc.terminate_connection(db, int(pid))
        if result:
            messages.success(request, _(f'Connection (PID {pid}) terminated.'))
        else:
            messages.error(request, _(f'Could not terminate PID {pid}.'))
    except Exception as e:
        messages.error(request, _(f'Error: {e}'))

    return redirect('tenants:pa_db_connections', pk=pk)


@platform_admin_required
@require_POST
def pa_db_kill_all_connections(request, pk):
    """Terminate ALL connections to a database."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    count = svc.terminate_all_connections(db)
    messages.success(request, _(f'Terminated {count} connection(s).'))

    return redirect('tenants:pa_db_connections', pk=pk)


# ── Locks ────────────────────────────────────────────────────────────────────

@platform_admin_required
def pa_db_locks(request, pk):
    """View current database locks."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    locks = svc.get_database_locks(db)

    context = pa_context(request, {
        'database': db,
        'locks': locks,
    })
    return render(request, 'platform_admin/db_ops/locks.html', context)


# ── Maintenance ──────────────────────────────────────────────────────────────

@platform_admin_required
def pa_db_maintenance(request, pk):
    """Database maintenance page (VACUUM, ANALYZE, REINDEX)."""
    db = get_object_or_404(TenantDatabase, pk=pk)

    logs = ServerLog.objects.filter(
        database=db,
        action='database_maintenance',
    ).order_by('-created_at')[:20]

    context = pa_context(request, {
        'database': db,
        'maintenance_logs': logs,
    })
    return render(request, 'platform_admin/db_ops/maintenance.html', context)


@platform_admin_required
@require_POST
def pa_db_run_maintenance(request, pk):
    """Execute a maintenance operation."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    operation = request.POST.get('operation', 'vacuum')
    allowed = ('vacuum', 'vacuum_full', 'analyze', 'vacuum_analyze', 'reindex')

    if operation not in allowed:
        messages.error(request, _('Invalid maintenance operation.'))
        return redirect('tenants:pa_db_maintenance', pk=pk)

    success, msg = svc.run_maintenance(db, operation)
    if success:
        messages.success(request, _(f'Maintenance ({operation}) completed: {msg}'))
    else:
        messages.error(request, _(f'Maintenance failed: {msg}'))

    return redirect('tenants:pa_db_maintenance', pk=pk)


# ── Export / Backup ──────────────────────────────────────────────────────────

@platform_admin_required
@require_POST
def pa_db_export(request, pk):
    """Export (pg_dump) a database and start download."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    success, result = svc.export_database(db)
    if success:
        # Serve the file
        filename = os.path.basename(result)
        response = FileResponse(open(result, 'rb'), content_type='application/sql')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    else:
        messages.error(request, _(f'Export failed: {result}'))
        return redirect('tenants:pa_database_detail', pk=pk)


# ── Import / Restore ────────────────────────────────────────────────────────

@platform_admin_required
@require_POST
def pa_db_import(request, pk):
    """Import a SQL file into a database."""
    db = get_object_or_404(TenantDatabase, pk=pk)

    sql_file = request.FILES.get('sql_file')
    if not sql_file:
        messages.error(request, _('Please upload a SQL file.'))
        return redirect('tenants:pa_database_detail', pk=pk)

    # Save uploaded file temporarily
    upload_dir = os.path.join(settings.BASE_DIR, 'media', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, sql_file.name)

    with open(filepath, 'wb+') as dest:
        for chunk in sql_file.chunks():
            dest.write(chunk)

    svc = DatabaseService()
    success, msg = svc.import_database(db, filepath)

    # Clean up
    if os.path.exists(filepath):
        os.remove(filepath)

    if success:
        messages.success(request, _('Database imported successfully.'))
    else:
        messages.error(request, _(f'Import failed: {msg}'))

    return redirect('tenants:pa_database_detail', pk=pk)


# ── Clone ────────────────────────────────────────────────────────────────────

@platform_admin_required
def pa_db_clone(request, pk):
    """Clone database form and execution."""
    db = get_object_or_404(TenantDatabase, pk=pk)

    if request.method == 'POST':
        new_name = request.POST.get('new_name', '').strip()
        new_display = request.POST.get('new_display_name', '').strip()

        if not new_name:
            messages.error(request, _('Please provide a database name.'))
        else:
            svc = DatabaseService()
            success, result = svc.clone_database(db, new_name, new_display or new_name, request.user)
            if success:
                messages.success(request, _(f'Database cloned successfully as {result.name}.'))
                return redirect('tenants:pa_database_detail', pk=result.pk)
            else:
                messages.error(request, _(f'Clone failed: {result}'))

    context = pa_context(request, {
        'database': db,
    })
    return render(request, 'platform_admin/db_ops/clone.html', context)


# ── Password Reset ───────────────────────────────────────────────────────────

@platform_admin_required
@require_POST
def pa_db_reset_password(request, pk):
    """Reset the database user password."""
    db = get_object_or_404(TenantDatabase, pk=pk)
    svc = DatabaseService()

    success, msg = svc.reset_database_password(db)
    if success:
        messages.success(request, _('Database password has been reset. Check the database detail for the new credentials.'))
    else:
        messages.error(request, _(f'Password reset failed: {msg}'))

    return redirect('tenants:pa_database_detail', pk=pk)


# ── Server Databases Overview ────────────────────────────────────────────────

@platform_admin_required
def pa_server_db_overview(request, pk):
    """All databases on a particular server, with sizes and connections."""
    from tenants.models import PostgresServer
    server = get_object_or_404(PostgresServer, pk=pk)
    svc = DatabaseService()

    overview = svc.get_server_databases_overview(server)
    pg_settings = svc.get_server_settings(server)

    context = pa_context(request, {
        'server': server,
        'databases_overview': overview,
        'pg_settings': pg_settings,
    })
    return render(request, 'platform_admin/db_ops/server_overview.html', context)
