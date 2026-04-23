"""Aggregated dashboard endpoint."""

from datetime import date

from django.db.models import Count, Q
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from rest_framework.decorators import api_view
from rest_framework.response import Response

from erp.models import Attendance, LeaveRequest, Notification, Payroll, Task

from ..base import _error, _get_employee


@api_view(['GET'])
@cache_page(60 * 5)   # 5 minutes
@vary_on_cookie
def mobile_dashboard(request):
    """Aggregated dashboard data."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    today = date.today()
    month_start = today.replace(day=1)

    # Today's attendance
    today_att = Attendance.objects.filter(employee=employee, date=today).first()

    # Month stats — single query with conditional aggregation
    month_agg = Attendance.objects.filter(
        employee=employee, date__gte=month_start, date__lte=today,
    ).aggregate(
        total_present=Count('id', filter=Q(is_present=True)),
        total_late=Count('id', filter=Q(is_late=True)),
    )
    total_present = month_agg['total_present']
    total_late = month_agg['total_late']
    total_days = (today - month_start).days + 1

    # Pending leaves + pending tasks + unread notifications — single query
    counts = {
        'pending_leaves': LeaveRequest.objects.filter(
            employee=employee, status='pending',
        ).count(),
        'pending_tasks': Task.objects.filter(
            assigned_to=employee, status__in=['todo', 'in_progress'],
        ).count(),
        'unread_notifications': Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count(),
    }

    # Recent payslips — select_related to avoid N+1 on FK access
    recent_payslips = Payroll.objects.filter(
        employee=employee, status__in=['approved', 'paid'],
    ).select_related('employee').order_by('-period_end')[:3]

    return Response({
        'today_attendance': {
            'checked_in': today_att is not None and today_att.check_in is not None,
            'checked_out': today_att is not None and today_att.check_out is not None,
            'check_in': str(today_att.check_in) if today_att and today_att.check_in else None,
            'check_out': str(today_att.check_out) if today_att and today_att.check_out else None,
            'is_late': today_att.is_late if today_att else False,
        } if today_att else None,
        'month_stats': {
            'total_days': total_days,
            'present': total_present,
            'absent': total_days - total_present,
            'late': total_late,
        },
        'pending_leaves': counts['pending_leaves'],
        'pending_tasks': counts['pending_tasks'],
        'unread_notifications': counts['unread_notifications'],
        'recent_payslips': [{
            'id': p.pk,
            'period_start': p.period_start.isoformat(),
            'period_end': p.period_end.isoformat(),
            'net_salary': str(p.net_salary),
            'status': p.status,
        } for p in recent_payslips],
    })
