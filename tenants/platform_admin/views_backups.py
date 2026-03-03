"""
Platform Admin - Backup Management Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from tenants.models import (
    PostgresServer, TenantDatabase, ServerLog,
)
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_backup_list(request):
    """Backup management overview."""
    databases = TenantDatabase.objects.filter(
        status='active'
    ).select_related('server').order_by('server__name', 'name')

    servers = PostgresServer.objects.filter(status='active').order_by('name')

    # Backup-related logs
    backup_logs = ServerLog.objects.filter(
        action__in=['database_backup', 'database_restore']
    ).select_related('server', 'database', 'user').order_by('-created_at')[:50]

    context = pa_context(request, {
        'databases': databases,
        'servers': servers,
        'backup_logs': backup_logs,
        'total_dbs': databases.count(),
    })
    return render(request, 'platform_admin/backups/list.html', context)


@platform_admin_required
@require_POST
def pa_backup_database(request, pk):
    """Trigger a backup for a specific database."""
    database = get_object_or_404(TenantDatabase, pk=pk, status='active')

    try:
        from tenants.services import DatabaseService
        db_service = DatabaseService()

        # Attempt backup
        backup_path = db_service.backup_database(database)

        ServerLog.objects.create(
            server=database.server,
            database=database,
            user=request.user,
            action='database_backup',
            level='success',
            message=f'Backup completed for {database.name}.',
            details={'backup_path': str(backup_path) if backup_path else ''},
        )
        messages.success(request, _(f'Backup of "{database.display_name or database.name}" completed.'))
    except AttributeError:
        # DatabaseService may not have backup_database method yet
        ServerLog.objects.create(
            server=database.server,
            database=database,
            user=request.user,
            action='database_backup',
            level='error',
            message=f'Backup method not available for {database.name}.',
        )
        messages.warning(request, _('Backup functionality is not yet configured in DatabaseService.'))
    except Exception as e:
        ServerLog.objects.create(
            server=database.server,
            database=database,
            user=request.user,
            action='database_backup',
            level='error',
            message=f'Backup failed for {database.name}: {e}',
        )
        messages.error(request, _(f'Backup failed: {e}'))

    return redirect('tenants:pa_backup_list')


@platform_admin_required
@require_POST
def pa_backup_all(request):
    """Trigger backup for all active databases."""
    databases = TenantDatabase.objects.filter(status='active')
    success_count = 0
    fail_count = 0

    try:
        from tenants.services import DatabaseService
        db_service = DatabaseService()

        for database in databases:
            try:
                db_service.backup_database(database)
                ServerLog.objects.create(
                    server=database.server,
                    database=database,
                    user=request.user,
                    action='database_backup',
                    level='success',
                    message=f'Bulk backup completed for {database.name}.',
                )
                success_count += 1
            except Exception as e:
                ServerLog.objects.create(
                    server=database.server,
                    database=database,
                    user=request.user,
                    action='database_backup',
                    level='error',
                    message=f'Bulk backup failed for {database.name}: {e}',
                )
                fail_count += 1
    except AttributeError:
        messages.warning(request, _('Backup functionality is not yet configured in DatabaseService.'))
        return redirect('tenants:pa_backup_list')

    messages.success(
        request,
        _(f'Bulk backup completed: {success_count} succeeded, {fail_count} failed.')
    )
    return redirect('tenants:pa_backup_list')
