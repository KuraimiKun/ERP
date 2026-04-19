"""
Mobile API Views for Employee Portal Flutter App.

All endpoints expect Token authentication and X-Tenant-DB header
(except login which resolves tenant from the user's DatabaseAssignment).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import authenticate
from django.db.models import Count, Q, Sum, Avg
from django.db.models.functions import Coalesce, ExtractHour
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from tenants.routers import get_tenant_db_alias, set_current_db_alias

from erp.models import (
    Employee, Attendance, LeaveRequest, LeaveType,
    Payroll, PayrollEarning, PayrollDeduction, AttendanceDevice,
    Task, TaskComment, Notification,
    POSTerminal, POSSession, POSOrder, POSOrderLine, POSPayment,
    Product, ProductCategory, Customer, PaymentMethod,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _get_employee(user):
    """Return the Employee record linked to the user, or None."""
    if hasattr(user, 'employee_profile') and user.employee_profile:
        return user.employee_profile
    try:
        return Employee.objects.get(email=user.email, approval_status='approved')
    except Employee.DoesNotExist:
        return None


def _employee_json(emp):
    """Serialize an Employee to a JSON-safe dict."""
    return {
        'id': emp.pk,
        'employee_id': emp.employee_id,
        'first_name': emp.first_name,
        'last_name': emp.last_name,
        'first_name_ar': emp.first_name_ar or '',
        'last_name_ar': emp.last_name_ar or '',
        'email': emp.email,
        'phone': emp.phone or '',
        'department': emp.department.name if emp.department else '',
        'department_ar': emp.department.name_ar if emp.department and hasattr(emp.department, 'name_ar') else '',
        'job_title': emp.job_title or '',
        'photo_url': emp.photo.url if emp.photo else '',
        'permissions': {
            'can_scan_qr': emp.portal_can_scan_qr,
            'can_view_attendance': emp.portal_can_view_attendance,
            'can_manage_leaves': emp.portal_can_manage_leaves,
            'can_view_payslips': emp.portal_can_view_payslips,
            'can_edit_profile': emp.portal_can_edit_profile,
            'can_view_tasks': emp.portal_can_view_tasks,
            'can_use_pos': emp.portal_can_use_pos,
        },
    }


def _error(msg, status=400):
    return Response({'error': msg}, status=status)


# ═══════════════════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def mobile_login(request):
    """
    Authenticate with email + password.
    Returns token, employee data, permissions, company info, and tenant_db.
    """
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    if not email or not password:
        return _error('Email and password are required.')

    user = authenticate(request, username=email, password=password)
    if not user:
        return _error('Invalid email or password.', 401)

    if not user.is_approved:
        return _error('Your account is not yet approved.', 403)

    # Resolve tenant DB
    db_alias = get_tenant_db_alias(user)
    if db_alias == 'default':
        return _error('No database assigned to your account.', 403)

    # Set tenant context to look up employee
    set_current_db_alias(db_alias)

    employee = _get_employee(user)
    if not employee:
        return _error('No employee profile found for your account.', 404)

    # Tokens live in the default DB — force it explicitly since tenant
    # context is already set and the router would send it to the wrong DB.
    token, _ = Token.objects.using('default').get_or_create(user=user)

    company = employee.company
    return Response({
        'token': token.key,
        'employee': _employee_json(employee),
        'company': {
            'id': company.pk,
            'name': company.name,
            'name_ar': company.name_ar if hasattr(company, 'name_ar') else '',
            'logo_url': company.logo.url if hasattr(company, 'logo') and company.logo else '',
        },
        'tenant_db': db_alias,
    })


@api_view(['POST'])
def mobile_logout(request):
    """Delete the current auth token."""
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    return Response({'success': True})


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# Profile
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'PATCH'])
def mobile_profile(request):
    """GET: employee profile. PATCH: update allowed fields."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if request.method == 'PATCH':
        if not employee.portal_can_edit_profile:
            return _error('You do not have permission to edit your profile.', 403)

        allowed_fields = [
            'phone', 'emergency_contact_name', 'emergency_contact_phone',
            'address', 'city', 'country',
        ]
        updated = []
        for field in allowed_fields:
            if field in request.data:
                setattr(employee, field, request.data[field])
                updated.append(field)

        if updated:
            employee.save(update_fields=updated + ['updated_at'])

    data = _employee_json(employee)
    data.update({
        'gender': employee.gender,
        'date_of_birth': employee.date_of_birth.isoformat() if employee.date_of_birth else None,
        'nationality': employee.nationality or '',
        'emergency_contact_name': employee.emergency_contact_name or '',
        'emergency_contact_phone': employee.emergency_contact_phone or '',
        'address': employee.address or '',
        'city': employee.city or '',
        'country': employee.country or '',
        'hire_date': employee.hire_date.isoformat() if employee.hire_date else None,
        'employment_type': employee.employment_type,
        'employment_status': employee.employment_status,
        'branch': employee.branch.name if employee.branch else '',
    })
    return Response(data)


@api_view(['POST'])
def mobile_change_password(request):
    """Change password. Requires current_password, new_password, confirm_password."""
    current_password = request.data.get('current_password', '')
    new_password = request.data.get('new_password', '')
    confirm_password = request.data.get('confirm_password', '')

    if not current_password or not new_password:
        return _error('Current password and new password are required.')

    if not request.user.check_password(current_password):
        return _error('Current password is incorrect.')

    if new_password != confirm_password:
        return _error('New passwords do not match.')

    if len(new_password) < 8:
        return _error('New password must be at least 8 characters.')

    request.user.set_password(new_password)
    request.user.save()

    # Regenerate token
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    token = Token.objects.create(user=request.user)

    return Response({'success': True, 'token': token.key})


# ═══════════════════════════════════════════════════════════════════════════
# Attendance
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def mobile_attendance_list(request):
    """Attendance history with date range filter."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_view_attendance:
        return _error('Permission denied.', 403)

    today = date.today()
    start_date = request.query_params.get('start_date', today.replace(day=1).isoformat())
    end_date = request.query_params.get('end_date', today.isoformat())

    attendances = Attendance.objects.filter(
        employee=employee, date__gte=start_date, date__lte=end_date,
    ).order_by('-date')

    stats = attendances.aggregate(
        present=Count('id', filter=Q(is_present=True)),
        late=Count('id', filter=Q(is_late=True)),
        absent=Count('id', filter=Q(is_present=False)),
    )

    return Response({
        'stats': stats,
        'start_date': start_date,
        'end_date': end_date,
        'attendances': [{
            'id': a.pk,
            'date': a.date.isoformat(),
            'check_in': str(a.check_in) if a.check_in else None,
            'check_out': str(a.check_out) if a.check_out else None,
            'hours_worked': str(a.hours_worked),
            'overtime_hours': str(a.overtime_hours),
            'is_present': a.is_present,
            'is_late': a.is_late,
            'late_minutes': a.late_minutes,
        } for a in attendances],
    })


@api_view(['POST'])
def mobile_attendance_scan(request):
    """Process QR code scan for check-in/check-out."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_scan_qr:
        return _error('Permission denied.', 403)

    # ── Rate-limit: 1 scan per 30 s per employee ──
    _SCAN_COOLDOWN = 30
    throttle_key = f"qr_scan:{employee.pk}"
    if cache.get(throttle_key):
        return _error('Please wait before scanning again.', 429)

    qr_data = request.data.get('qr_data', '')
    if not qr_data:
        return _error('No QR code data provided.')

    # The kiosk encodes a full URL (scan_url) into the QR image so that
    # browsers can tap it directly.  The mobile app scans the same QR and
    # sends the raw string, which may be the full URL.  Extract the payload
    # from the ?qr= query parameter when present.
    if '?qr=' in qr_data:
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(qr_data).query)
        qr_data = qs.get('qr', [''])[0]

    try:
        device = AttendanceDevice.verify_qr_payload(qr_data, max_age=30)
    except ValueError as e:
        return _error(str(e))

    if employee.company_id != device.company_id:
        return _error('This device does not belong to your company.')

    today = timezone.now().date()
    now_time = timezone.now().time()

    # ── Duplicate check-in guard ──
    existing = Attendance.objects.filter(employee=employee, date=today).first()
    if existing and existing.check_in:
        last_ts = datetime.combine(today, existing.check_out or existing.check_in)
        elapsed = (datetime.combine(today, now_time) - last_ts).total_seconds()
        if elapsed < _SCAN_COOLDOWN:
            return _error('Duplicate scan detected. Try again shortly.', 429)

    # Mark cooldown AFTER validation passes
    cache.set(throttle_key, 1, _SCAN_COOLDOWN)

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={'check_in': now_time, 'is_present': True},
    )

    action = 'check_in'

    if created:
        if device.work_start_time:
            start_dt = datetime.combine(today, device.work_start_time)
            threshold_dt = start_dt + timedelta(minutes=device.late_threshold_minutes)
            check_in_dt = datetime.combine(today, now_time)
            if check_in_dt > threshold_dt:
                attendance.is_late = True
                attendance.late_minutes = int(
                    (check_in_dt - start_dt).total_seconds() / 60
                )
                attendance.save(update_fields=['is_late', 'late_minutes'])
    else:
        action = 'check_out'
        attendance.check_out = now_time
        if attendance.check_in:
            cin = datetime.combine(today, attendance.check_in)
            cout = datetime.combine(today, now_time)
            diff = (cout - cin).total_seconds() / 3600
            attendance.hours_worked = Decimal(str(round(diff, 2)))
            if device.work_start_time and device.work_end_time:
                standard = (
                    datetime.combine(today, device.work_end_time)
                    - datetime.combine(today, device.work_start_time)
                ).total_seconds() / 3600
                if diff > standard:
                    attendance.overtime_hours = Decimal(str(round(diff - standard, 2)))
        attendance.save()

    return Response({
        'success': True,
        'action': action,
        'attendance': {
            'date': attendance.date.isoformat(),
            'check_in': str(attendance.check_in) if attendance.check_in else None,
            'check_out': str(attendance.check_out) if attendance.check_out else None,
            'is_late': attendance.is_late,
            'late_minutes': attendance.late_minutes,
            'hours_worked': str(attendance.hours_worked),
        },
    })


# ═══════════════════════════════════════════════════════════════════════════
# Leave Requests
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# Payslips
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def mobile_payslip_list(request):
    """List payslips (approved/paid only)."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_view_payslips:
        return _error('Permission denied.', 403)

    payrolls = Payroll.objects.filter(
        employee=employee, status__in=['approved', 'paid'],
    ).order_by('-period_end')

    return Response({
        'payslips': [{
            'id': p.pk,
            'period_start': p.period_start.isoformat(),
            'period_end': p.period_end.isoformat(),
            'basic_salary': str(p.basic_salary),
            'gross_salary': str(p.gross_salary),
            'total_deductions': str(p.total_deductions),
            'net_salary': str(p.net_salary),
            'status': p.status,
            'payment_date': p.payment_date.isoformat() if p.payment_date else None,
        } for p in payrolls],
    })


@api_view(['GET'])
def mobile_payslip_detail(request, pk):
    """Payslip detail with earnings and deductions breakdown."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_view_payslips:
        return _error('Permission denied.', 403)

    try:
        payroll = Payroll.objects.get(
            pk=pk, employee=employee, status__in=['approved', 'paid'],
        )
    except Payroll.DoesNotExist:
        return _error('Payslip not found.', 404)

    earnings = PayrollEarning.objects.filter(payroll=payroll)
    deductions = PayrollDeduction.objects.filter(payroll=payroll)

    return Response({
        'payslip': {
            'id': payroll.pk,
            'period_start': payroll.period_start.isoformat(),
            'period_end': payroll.period_end.isoformat(),
            'basic_salary': str(payroll.basic_salary),
            'gross_salary': str(payroll.gross_salary),
            'total_deductions': str(payroll.total_deductions),
            'net_salary': str(payroll.net_salary),
            'status': payroll.status,
            'payment_date': payroll.payment_date.isoformat() if payroll.payment_date else None,
            'payment_reference': payroll.payment_reference or '',
        },
        'earnings': [{
            'type': e.get_earning_type_display(),
            'description': e.description or '',
            'amount': str(e.amount),
        } for e in earnings],
        'deductions': [{
            'type': d.get_deduction_type_display(),
            'description': d.description or '',
            'amount': str(d.amount),
        } for d in deductions],
    })


# ═══════════════════════════════════════════════════════════════════════════
# Tasks
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def mobile_notifications(request):
    """List notifications for the user."""
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).order_by('-created_at')[:50]

    return Response({
        'notifications': [{
            'id': n.pk,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
            'action_url': n.action_url or '',
        } for n in notifications],
        'unread_count': Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count(),
    })


@api_view(['POST'])
def mobile_notifications_read(request):
    """Mark notification(s) as read."""
    notification_ids = request.data.get('ids', [])
    mark_all = request.data.get('all', False)

    if mark_all:
        Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).update(is_read=True, read_at=timezone.now())
    elif notification_ids:
        Notification.objects.filter(
            recipient=request.user, pk__in=notification_ids,
        ).update(is_read=True, read_at=timezone.now())

    return Response({'success': True})


# ═══════════════════════════════════════════════════════════════════════════
# POS - Terminals & Sessions
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def mobile_pos_terminals(request):
    """List available POS terminals for this employee."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    terminals = POSTerminal.objects.filter(
        company=employee.company, is_active=True,
    )

    result = []
    for t in terminals:
        if not t.allowed_employees.exists() or t.allowed_employees.filter(pk=employee.pk).exists():
            open_session = POSSession.objects.filter(terminal=t, status='open').first()
            result.append({
                'id': t.pk,
                'code': t.code,
                'name': t.name,
                'name_ar': t.name_ar or '',
                'location': t.location or '',
                'has_open_session': open_session is not None,
                'open_session_id': open_session.pk if open_session else None,
                'open_session_number': open_session.session_number if open_session else None,
            })

    return Response({'terminals': result})


@api_view(['POST'])
def mobile_pos_session_open(request):
    """Open a new POS session."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    terminal_id = request.data.get('terminal_id')
    opening_balance = request.data.get('opening_balance', '0')

    try:
        terminal = POSTerminal.objects.get(
            pk=terminal_id, company=employee.company, is_active=True,
        )
    except POSTerminal.DoesNotExist:
        return _error('Terminal not found.')

    from erp.services.pos import open_session
    try:
        session = open_session(
            company=employee.company,
            terminal=terminal,
            employee=employee,
            opening_balance=opening_balance,
        )
    except ValueError as e:
        return _error(str(e))

    return Response({
        'success': True,
        'session': {
            'id': session.pk,
            'session_number': session.session_number,
            'terminal_name': terminal.name,
            'opening_balance': str(session.opening_balance),
            'opened_at': session.opened_at.isoformat() if session.opened_at else None,
        },
    }, status=201)


@api_view(['GET'])
def mobile_pos_session_detail(request, pk):
    """Get session info."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    try:
        session = POSSession.objects.select_related('terminal').get(
            pk=pk, company=employee.company,
        )
    except POSSession.DoesNotExist:
        return _error('Session not found.', 404)

    session.calculate_expected_cash()

    orders = session.orders.filter(status='completed')
    order_count = orders.count()
    total_sales = orders.aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0'))
    )['total']

    return Response({
        'session': {
            'id': session.pk,
            'session_number': session.session_number,
            'terminal_name': session.terminal.name,
            'status': session.status,
            'opening_balance': str(session.opening_balance),
            'expected_cash': str(session.expected_cash),
            'total_sales': str(total_sales),
            'order_count': order_count,
            'opened_at': session.opened_at.isoformat() if session.opened_at else None,
            'closed_at': session.closed_at.isoformat() if session.closed_at else None,
        },
    })


@api_view(['POST'])
def mobile_pos_session_close(request, pk):
    """Close a POS session."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    try:
        session = POSSession.objects.get(
            pk=pk, company=employee.company, status='open',
        )
    except POSSession.DoesNotExist:
        return _error('Session not found or already closed.', 404)

    closing_balance = request.data.get('closing_balance', '0')
    notes = request.data.get('notes', '')

    from erp.services.pos import close_session
    session = close_session(
        session=session,
        employee=employee,
        closing_balance=closing_balance,
        notes=notes,
    )

    return Response({
        'success': True,
        'session': {
            'id': session.pk,
            'session_number': session.session_number,
            'status': session.status,
            'total_sales': str(session.total_sales),
            'total_orders': session.total_orders,
            'expected_cash': str(session.expected_cash),
            'closing_balance': str(session.closing_balance),
            'cash_difference': str(session.cash_difference),
        },
    })


# ═══════════════════════════════════════════════════════════════════════════
# POS - Products, Categories, Customers
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
def mobile_pos_products(request):
    """Search products for POS."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    company = employee.company
    q = request.query_params.get('q', '').strip()
    category_id = request.query_params.get('category', '')
    barcode = request.query_params.get('barcode', '').strip()

    products = Product.objects.filter(
        company=company, is_active=True,
    ).select_related('category', 'tax_rate')

    if barcode:
        products = products.filter(barcode=barcode)
    elif q:
        products = products.filter(
            Q(name__icontains=q) | Q(name_ar__icontains=q) |
            Q(sku__icontains=q) | Q(barcode__icontains=q)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    products = products[:50]

    return Response({
        'products': [{
            'id': p.pk,
            'sku': p.sku,
            'barcode': p.barcode or '',
            'name': p.name,
            'name_ar': p.name_ar or '',
            'selling_price': str(p.selling_price),
            'cost_price': str(p.cost_price or 0),
            'min_selling_price': str(p.min_selling_price or 0),
            'tax_rate_id': p.tax_rate_id,
            'tax_rate_percent': str(p.tax_rate.rate) if p.tax_rate else '0',
            'track_inventory': p.track_inventory,
            'quantity_on_hand': str(p.quantity_on_hand),
            'image_url': p.image.url if p.image else '',
            'category_id': p.category_id,
            'category_name': p.category.name if p.category else '',
        } for p in products],
    })


@api_view(['GET'])
def mobile_pos_categories(request):
    """List product categories."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    categories = ProductCategory.objects.filter(
        company=employee.company, is_active=True,
    ).order_by('sort_order', 'name')

    return Response({
        'categories': [{
            'id': c.pk,
            'name': c.name,
            'name_ar': c.name_ar or '',
            'code': c.code or '',
        } for c in categories],
    })


@api_view(['GET'])
def mobile_pos_customers(request):
    """Search customers for POS."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    q = request.query_params.get('q', '').strip()
    customers = Customer.objects.filter(company=employee.company, is_active=True)
    if q:
        customers = customers.filter(
            Q(name__icontains=q) | Q(name_ar__icontains=q) |
            Q(customer_id__icontains=q) | Q(phone__icontains=q)
        )
    customers = customers[:20]

    return Response({
        'customers': [{
            'id': c.pk,
            'customer_id': c.customer_id,
            'name': c.name,
            'name_ar': c.name_ar or '',
            'phone': c.phone or '',
        } for c in customers],
    })


@api_view(['GET'])
def mobile_pos_payment_methods(request):
    """List payment methods."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    methods = PaymentMethod.objects.filter(
        company=employee.company, is_active=True,
    )

    return Response({
        'payment_methods': [{
            'id': m.pk,
            'name': m.name,
            'name_ar': m.name_ar if hasattr(m, 'name_ar') else '',
            'code': m.code,
            'requires_reference': m.requires_reference if hasattr(m, 'requires_reference') else False,
        } for m in methods],
    })


# ═══════════════════════════════════════════════════════════════════════════
# POS - Orders
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
def mobile_pos_create_order(request):
    """Create a POS order from cart data."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    session_id = request.data.get('session_id')
    cart_items = request.data.get('items', [])
    customer_id = request.data.get('customer_id')
    discount_percent = Decimal(str(request.data.get('discount_percent', 0)))
    discount_amount = Decimal(str(request.data.get('discount_amount', 0)))
    notes = request.data.get('notes', '')

    if not cart_items:
        return _error('Cart is empty.')

    try:
        session = POSSession.objects.get(
            pk=session_id, company=employee.company, status='open',
        )
    except POSSession.DoesNotExist:
        return _error('Session not found or closed.')

    customer = None
    if customer_id:
        try:
            customer = Customer.objects.get(pk=customer_id, company=employee.company)
        except Customer.DoesNotExist:
            pass

    from erp.services.pos import create_pos_order
    try:
        order = create_pos_order(
            session=session,
            employee=employee,
            cart_items=cart_items,
            customer=customer,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            notes=notes,
        )
    except Exception as e:
        return _error(str(e))

    return Response({
        'success': True,
        'order_id': order.pk,
        'order_number': order.order_number,
        'total_amount': str(order.total_amount),
        'subtotal': str(order.subtotal),
        'tax_amount': str(order.tax_amount),
        'discount_amount': str(order.discount_amount),
    }, status=201)


@api_view(['POST'])
def mobile_pos_complete_order(request):
    """Process payment and complete order."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    order_id = request.data.get('order_id')
    payments_data = request.data.get('payments', [])

    if not payments_data:
        return _error('No payment data provided.')

    try:
        order = POSOrder.objects.get(
            pk=order_id, company=employee.company, status='draft',
        )
    except POSOrder.DoesNotExist:
        return _error('Order not found or already completed.')

    from erp.services.pos import complete_pos_order
    try:
        order = complete_pos_order(order=order, payments_data=payments_data)
    except ValueError as e:
        return _error(str(e))

    payments = order.payments.select_related('payment_method').all()

    return Response({
        'success': True,
        'order_id': order.pk,
        'order_number': order.order_number,
        'status': order.status,
        'total_amount': str(order.total_amount),
        'payments': [{
            'method': p.payment_method.name,
            'method_code': p.payment_method.code,
            'amount': str(p.amount),
            'tendered': str(p.tendered),
            'change': str(p.change_amount),
        } for p in payments],
    })


@api_view(['GET'])
def mobile_pos_receipt(request, pk):
    """Get receipt data as JSON."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    try:
        order = POSOrder.objects.select_related(
            'session__terminal', 'customer', 'employee',
        ).get(pk=pk, company=employee.company)
    except POSOrder.DoesNotExist:
        return _error('Order not found.', 404)

    lines = order.lines.select_related('product').all()
    payments = order.payments.select_related('payment_method').all()
    terminal = order.session.terminal

    return Response({
        'receipt': {
            'order_number': order.order_number,
            'order_date': order.order_date.isoformat(),
            'status': order.status,
            'terminal_name': terminal.name,
            'receipt_header': terminal.receipt_header or '',
            'receipt_footer': terminal.receipt_footer or '',
            'employee_name': str(order.employee) if order.employee else '',
            'customer_name': order.customer.name if order.customer else '',
            'subtotal': str(order.subtotal),
            'discount_amount': str(order.discount_amount),
            'tax_amount': str(order.tax_amount),
            'total_amount': str(order.total_amount),
            'lines': [{
                'product_name': l.product_name,
                'product_sku': l.product_sku,
                'quantity': str(l.quantity),
                'unit_price': str(l.unit_price),
                'discount_percent': str(l.discount_percent),
                'tax_amount': str(l.tax_amount),
                'line_total': str(l.line_total),
            } for l in lines],
            'payments': [{
                'method': p.payment_method.name,
                'amount': str(p.amount),
                'tendered': str(p.tendered),
                'change': str(p.change_amount),
            } for p in payments],
            'company_name': employee.company.name,
            'company_name_ar': employee.company.name_ar if hasattr(employee.company, 'name_ar') else '',
        },
    })


@api_view(['GET'])
def mobile_pos_order_history(request, session_id):
    """Orders for a session."""
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    try:
        session = POSSession.objects.get(pk=session_id, company=employee.company)
    except POSSession.DoesNotExist:
        return _error('Session not found.', 404)

    orders = session.orders.select_related('customer', 'employee').order_by('-order_date')

    return Response({
        'orders': [{
            'id': o.pk,
            'order_number': o.order_number,
            'order_date': o.order_date.isoformat(),
            'customer_name': o.customer.name if o.customer else '',
            'total_amount': str(o.total_amount),
            'status': o.status,
        } for o in orders],
    })


# ═══════════════════════════════════════════════════════════════════════════
# POS - Stats / Performance
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@cache_page(60 * 5)   # 5 minutes
@vary_on_cookie
def mobile_pos_stats(request):
    """
    Employee POS performance statistics.

    Query params:
        period: today | week | month  (default: today)
    """
    employee = _get_employee(request.user)
    if not employee:
        return _error('No employee profile found.', 404)

    if not employee.portal_can_use_pos:
        return _error('Permission denied.', 403)

    period = request.query_params.get('period', 'today')
    today = timezone.now().date()

    if period == 'week':
        start_date = today - timedelta(days=today.weekday())
    elif period == 'month':
        start_date = today.replace(day=1)
    else:
        start_date = today

    # Base queryset: completed orders by this employee in date range
    orders_qs = POSOrder.objects.filter(
        employee=employee,
        status='completed',
        order_date__date__gte=start_date,
        order_date__date__lte=today,
    )

    # Summary
    summary = orders_qs.aggregate(
        total_sales=Coalesce(Sum('total_amount'), Decimal('0')),
        total_orders=Count('id'),
        average_order=Coalesce(Avg('total_amount'), Decimal('0')),
        total_discount=Coalesce(Sum('discount_amount'), Decimal('0')),
        total_tax=Coalesce(Sum('tax_amount'), Decimal('0')),
    )

    # Items sold
    total_items = POSOrderLine.objects.filter(
        order__in=orders_qs,
    ).aggregate(
        total=Coalesce(Sum('quantity'), Decimal('0')),
    )['total']

    # Refunds
    refund_qs = POSOrder.objects.filter(
        employee=employee,
        status='refunded',
        order_date__date__gte=start_date,
        order_date__date__lte=today,
    )
    refund_stats = refund_qs.aggregate(
        total_refunds=Coalesce(Sum('total_amount'), Decimal('0')),
        refund_count=Count('id'),
    )

    # Payment breakdown
    payment_breakdown = POSPayment.objects.filter(
        order__in=orders_qs,
    ).values(
        'payment_method__name',
        'payment_method__code',
    ).annotate(
        total=Sum('amount'),
        count=Count('id'),
    ).order_by('-total')

    payment_list = []
    for pb in payment_breakdown:
        payment_list.append({
            'method': pb['payment_method__name'],
            'code': pb['payment_method__code'],
            'total': str(pb['total']),
            'count': pb['count'],
        })

    # Top products
    top_products = POSOrderLine.objects.filter(
        order__in=orders_qs,
    ).values(
        'product__name', 'product__sku',
    ).annotate(
        quantity=Sum('quantity'),
        total=Sum('line_total'),
    ).order_by('-total')[:5]

    top_list = [{
        'name': tp['product__name'],
        'sku': tp['product__sku'],
        'quantity': str(tp['quantity']),
        'total': str(tp['total']),
    } for tp in top_products]

    # Recent sessions
    recent_sessions = POSSession.objects.filter(
        opened_by=employee,
    ).select_related('terminal').order_by('-opened_at')[:10]

    session_list = [{
        'id': s.pk,
        'session_number': s.session_number,
        'terminal_name': s.terminal.name,
        'opened_at': s.opened_at.isoformat() if s.opened_at else None,
        'closed_at': s.closed_at.isoformat() if s.closed_at else None,
        'status': s.status,
        'total_sales': str(s.total_sales or 0),
        'total_orders': s.total_orders or 0,
        'cash_difference': str(s.cash_difference or 0),
    } for s in recent_sessions]

    # Hourly sales
    hourly = orders_qs.annotate(
        hour=ExtractHour('order_date'),
    ).values('hour').annotate(
        total=Sum('total_amount'),
        count=Count('id'),
    ).order_by('hour')

    hourly_list = [{
        'hour': h['hour'],
        'total': str(h['total']),
        'count': h['count'],
    } for h in hourly]

    return Response({
        'period': period,
        'summary': {
            'total_sales': str(summary['total_sales']),
            'total_orders': summary['total_orders'],
            'average_order': str(summary['average_order'].quantize(Decimal('0.01'))),
            'total_items_sold': str(total_items),
            'total_discount': str(summary['total_discount']),
            'total_tax': str(summary['total_tax']),
            'total_refunds': str(refund_stats['total_refunds']),
            'refund_count': refund_stats['refund_count'],
        },
        'payment_breakdown': payment_list,
        'top_products': top_list,
        'recent_sessions': session_list,
        'hourly_sales': hourly_list,
    })
