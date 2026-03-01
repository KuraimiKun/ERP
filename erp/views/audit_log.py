"""
ERP Views – Audit Log Viewer

Filterable list of all AuditLog entries.
"""

from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from erp.models import AuditLog
from ._common import (
    render, staff_member_required,
)

User = get_user_model()


@staff_member_required
def audit_log_list(request):
    """Paginated audit log with filters."""
    qs = AuditLog.objects.select_related('user', 'content_type').order_by('-created_at')

    # Filters
    user_id = request.GET.get('user', '')
    if user_id:
        qs = qs.filter(user_id=user_id)

    action = request.GET.get('action', '')
    if action:
        qs = qs.filter(action=action)

    date_from = request.GET.get('date_from', '')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)

    date_to = request.GET.get('date_to', '')
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(object_repr__icontains=search)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page', 1))

    # Build query string for pagination links (strip 'page' param)
    qd = request.GET.copy()
    qd.pop('page', None)
    query_string = qd.urlencode()

    users = User.objects.filter(
        pk__in=AuditLog.objects.values_list('user_id', flat=True).distinct()
    ).order_by('email')

    return render(request, 'erp/audit_log/list.html', {
        'page_obj': page,
        'query_string': query_string,
        'action_choices': AuditLog.Action.choices,
        'users': users,
        'current_user_id': user_id,
        'current_action': action,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'current_search': search,
    })
