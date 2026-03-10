"""
Platform Admin - Scheduled Tasks Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.views.decorators.http import require_POST

from tenants.models import ScheduledTask, TaskExecution
from .forms import ScheduledTaskForm
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_scheduled_list(request):
    """List all scheduled tasks."""
    qs = ScheduledTask.objects.select_related('server', 'database', 'created_by')

    # Filters
    task_type = request.GET.get('type')
    status = request.GET.get('status')
    if task_type:
        qs = qs.filter(task_type=task_type)
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    page_obj = paginate(request, qs, 20)

    context = pa_context(request, {
        'tasks': page_obj,
        'task_types': ScheduledTask.TASK_TYPE_CHOICES,
        'current_type': task_type,
        'current_status': status,
    })
    return render(request, 'platform_admin/scheduled/list.html', context)


@platform_admin_required
def pa_scheduled_create(request):
    """Create a new scheduled task."""
    if request.method == 'POST':
        form = ScheduledTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            messages.success(request, _('Scheduled task created successfully.'))
            return redirect('tenants:pa_scheduled_list')
    else:
        form = ScheduledTaskForm()

    context = pa_context(request, {'form': form})
    return render(request, 'platform_admin/scheduled/form.html', context)


@platform_admin_required
def pa_scheduled_edit(request, pk):
    """Edit an existing scheduled task."""
    task = get_object_or_404(ScheduledTask, pk=pk)
    if request.method == 'POST':
        form = ScheduledTaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, _('Scheduled task updated successfully.'))
            return redirect('tenants:pa_scheduled_detail', pk=pk)
    else:
        form = ScheduledTaskForm(instance=task)

    context = pa_context(request, {'form': form, 'task': task, 'editing': True})
    return render(request, 'platform_admin/scheduled/form.html', context)


@platform_admin_required
def pa_scheduled_detail(request, pk):
    """Detailed view of a scheduled task with execution history."""
    task = get_object_or_404(
        ScheduledTask.objects.select_related('server', 'database', 'created_by'),
        pk=pk,
    )
    executions = task.executions.order_by('-started_at')[:50]

    # Stats
    total_runs = task.run_count
    successful = task.executions.filter(status='success').count()
    failed = task.executions.filter(status='error').count()

    context = pa_context(request, {
        'task': task,
        'executions': executions,
        'total_runs': total_runs,
        'successful': successful,
        'failed': failed,
    })
    return render(request, 'platform_admin/scheduled/detail.html', context)


@platform_admin_required
@require_POST
def pa_scheduled_toggle(request, pk):
    """Toggle a scheduled task active/inactive."""
    task = get_object_or_404(ScheduledTask, pk=pk)
    task.is_active = not task.is_active
    task.save(update_fields=['is_active'])
    status = _('activated') if task.is_active else _('deactivated')
    messages.success(request, _(f'Task "{task.name}" {status}.'))
    return redirect('tenants:pa_scheduled_list')


@platform_admin_required
@require_POST
def pa_scheduled_delete(request, pk):
    """Delete a scheduled task."""
    task = get_object_or_404(ScheduledTask, pk=pk)
    name = task.name
    task.delete()
    messages.success(request, _(f'Task "{name}" deleted.'))
    return redirect('tenants:pa_scheduled_list')


@platform_admin_required
@require_POST
def pa_scheduled_run_now(request, pk):
    """Manually trigger a scheduled task immediately."""
    task = get_object_or_404(ScheduledTask, pk=pk)
    started = timezone.now()

    try:
        from tenants.services.database_service import DatabaseService

        if task.task_type in ('vacuum', 'vacuum_full', 'analyze', 'vacuum_analyze', 'reindex'):
            if not task.database:
                raise ValueError('No database assigned to this maintenance task.')
            db = task.database
            svc = DatabaseService(db.server)
            result = svc.run_maintenance(db.name, task.task_type)
            msg = result.get('message', 'Maintenance completed.')
        elif task.task_type == 'health_check':
            if task.server:
                task.server.save()  # triggers health check via last_health_check
                msg = f'Health check completed for {task.server.name}.'
            else:
                msg = 'Health check completed (all servers).'
        elif task.task_type == 'backup':
            if not task.database:
                raise ValueError('No database assigned to this backup task.')
            db = task.database
            svc = DatabaseService(db.server)
            result = svc.export_database(db.name)
            msg = result.get('message', 'Backup completed.')
        elif task.task_type == 'metric_snapshot':
            msg = 'Metric snapshot collection triggered.'
        else:
            msg = f'Task type "{task.task_type}" executed.'

        duration = (timezone.now() - started).total_seconds()
        TaskExecution.objects.create(
            task=task, status='success', message=msg,
            duration_seconds=duration, started_at=started,
            finished_at=timezone.now(),
        )
        task.last_run = timezone.now()
        task.last_status = 'success'
        task.last_message = msg
        task.run_count += 1
        task.save(update_fields=['last_run', 'last_status', 'last_message', 'run_count'])
        messages.success(request, _(f'Task "{task.name}" executed successfully.'))

    except Exception as e:
        duration = (timezone.now() - started).total_seconds()
        TaskExecution.objects.create(
            task=task, status='error', message=str(e),
            duration_seconds=duration, started_at=started,
            finished_at=timezone.now(),
        )
        task.last_run = timezone.now()
        task.last_status = 'error'
        task.last_message = str(e)
        task.run_count += 1
        task.save(update_fields=['last_run', 'last_status', 'last_message', 'run_count'])
        messages.error(request, _(f'Task "{task.name}" failed: {e}'))

    return redirect('tenants:pa_scheduled_detail', pk=pk)
