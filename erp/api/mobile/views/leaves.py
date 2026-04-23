"""Leave request endpoints."""

from datetime import date

from django.db.models import Sum
from rest_framework.decorators import api_view
from rest_framework.response import Response

from erp.models import LeaveRequest, LeaveType

from ..base import _error, _get_employee


@api_view(['GET', 'POST'])
def mobile_leaves(request):
    """
    GET: List leave requests with balances.
    POST: Create a new leave request.
    """
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_manage_leaves:
        return _error('Permission denied.', 403)

    if request.method == 'POST':
        leave_type_id = request.data.get('leave_type_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        reason = request.data.get('reason', '')

        if not leave_type_id or not start_date or not end_date:
            return _error('leave_type_id, start_date, and end_date are required.')

        try:
            leave_type = LeaveType.objects.get(pk=leave_type_id, is_active=True)
        except LeaveType.DoesNotExist:
            return _error('Leave type not found.')

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError:
            return _error('Invalid date format. Use YYYY-MM-DD.')

        if end < start:
            return _error('End date cannot be before start date.')

        days = (end - start).days + 1

        leave = LeaveRequest.objects.create(
            employee=employee,
            leave_type=leave_type,
            start_date=start,
            end_date=end,
            days_requested=days,
            reason=reason,
            status='pending',
        )

        return Response({
            'success': True,
            'leave': {
                'id': leave.pk,
                'leave_type': leave_type.name,
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'days_requested': days,
                'status': 'pending',
            },
        }, status=201)

    # GET
    status_filter = request.query_params.get('status', '')
    leaves = LeaveRequest.objects.filter(employee=employee).select_related('leave_type').order_by('-created_at')
    if status_filter:
        leaves = leaves.filter(status=status_filter)

    # Leave balances
    leave_balances = []
    for lt in LeaveType.objects.filter(is_active=True):
        used = LeaveRequest.objects.filter(
            employee=employee,
            leave_type=lt,
            status__in=['pending', 'approved'],
            start_date__year=date.today().year,
        ).aggregate(total=Sum('days_requested'))['total'] or 0
        leave_balances.append({
            'leave_type_id': lt.pk,
            'name': lt.name,
            'name_ar': lt.name_ar or '',
            'days_allowed': lt.days_allowed,
            'used': float(used),
            'remaining': max(lt.days_allowed - float(used), 0),
            'color': lt.color,
        })

    return Response({
        'leaves': [{
            'id': l.pk,
            'leave_type': l.leave_type.name,
            'leave_type_ar': l.leave_type.name_ar or '',
            'start_date': l.start_date.isoformat(),
            'end_date': l.end_date.isoformat(),
            'days_requested': float(l.days_requested),
            'reason': l.reason or '',
            'status': l.status,
            'created_at': l.created_at.isoformat(),
        } for l in leaves],
        'balances': leave_balances,
        'leave_types': [{
            'id': lt.pk,
            'name': lt.name,
            'name_ar': lt.name_ar or '',
            'days_allowed': lt.days_allowed,
        } for lt in LeaveType.objects.filter(is_active=True)],
    })


@api_view(['POST'])
def mobile_leave_cancel(request, pk):
    """Cancel a pending leave request."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_manage_leaves:
        return _error('Permission denied.', 403)

    try:
        leave = LeaveRequest.objects.get(pk=pk, employee=employee)
    except LeaveRequest.DoesNotExist:
        return _error('Leave request not found.', 404)

    if leave.status != 'pending':
        return _error('Only pending requests can be cancelled.')

    leave.status = 'cancelled'
    leave.save(update_fields=['status'])

    return Response({'success': True})
