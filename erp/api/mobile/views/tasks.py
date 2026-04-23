"""Task list, detail, status, and comment endpoints."""

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from erp.models import Task, TaskComment

from ..base import _error, _get_employee


@api_view(['GET'])
def mobile_task_list(request):
    """Tasks assigned to the employee."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_view_tasks:
        return _error('Permission denied.', 403)

    status_filter = request.query_params.get('status', '')
    tasks = Task.objects.filter(assigned_to=employee).order_by('-created_at')
    if status_filter:
        tasks = tasks.filter(status=status_filter)

    task_counts = {
        'total': tasks.count(),
        'todo': Task.objects.filter(assigned_to=employee, status='todo').count(),
        'in_progress': Task.objects.filter(assigned_to=employee, status='in_progress').count(),
        'completed': Task.objects.filter(assigned_to=employee, status='completed').count(),
    }

    return Response({
        'counts': task_counts,
        'tasks': [{
            'id': t.pk,
            'title': t.title,
            'description': t.description or '',
            'priority': t.priority,
            'status': t.status,
            'due_date': t.due_date.isoformat() if t.due_date else None,
            'completed_date': t.completed_date.isoformat() if t.completed_date else None,
            'created_at': t.created_at.isoformat(),
            'comment_count': t.comments.count(),
        } for t in tasks],
        'statuses': [{'value': s[0], 'label': s[1]} for s in Task.Status.choices],
    })


@api_view(['GET'])
def mobile_task_detail(request, pk):
    """Task detail with comments."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_view_tasks:
        return _error('Permission denied.', 403)

    try:
        task = Task.objects.get(pk=pk, assigned_to=employee)
    except Task.DoesNotExist:
        return _error('Task not found.', 404)

    comments = task.comments.select_related('author').order_by('created_at')

    return Response({
        'task': {
            'id': task.pk,
            'title': task.title,
            'description': task.description or '',
            'priority': task.priority,
            'status': task.status,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'completed_date': task.completed_date.isoformat() if task.completed_date else None,
            'created_at': task.created_at.isoformat(),
        },
        'comments': [{
            'id': c.pk,
            'author': c.author.get_full_name() or c.author.email,
            'content': c.content,
            'created_at': c.created_at.isoformat(),
        } for c in comments],
        'statuses': [{'value': s[0], 'label': s[1]} for s in Task.Status.choices],
    })


@api_view(['POST'])
def mobile_task_status(request, pk):
    """Update task status."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_view_tasks:
        return _error('Permission denied.', 403)

    try:
        task = Task.objects.get(pk=pk, assigned_to=employee)
    except Task.DoesNotExist:
        return _error('Task not found.', 404)

    new_status = request.data.get('status', '')
    valid_statuses = [s[0] for s in Task.Status.choices]
    if new_status not in valid_statuses:
        return _error(f'Invalid status. Must be one of: {", ".join(valid_statuses)}')

    task.status = new_status
    if new_status == 'completed':
        task.completed_date = timezone.now()
    task.save(update_fields=['status', 'completed_date'])

    return Response({'success': True, 'status': task.status})


@api_view(['POST'])
def mobile_task_comment(request, pk):
    """Add a comment to a task."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_view_tasks:
        return _error('Permission denied.', 403)

    try:
        task = Task.objects.get(pk=pk, assigned_to=employee)
    except Task.DoesNotExist:
        return _error('Task not found.', 404)

    content = request.data.get('content', '').strip()
    if not content:
        return _error('Comment content is required.')

    comment = TaskComment.objects.create(
        task=task,
        author=request.user,
        content=content,
    )

    return Response({
        'success': True,
        'comment': {
            'id': comment.pk,
            'author': request.user.get_full_name() or request.user.email,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
        },
    }, status=201)
