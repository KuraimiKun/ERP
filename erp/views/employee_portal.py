"""
ERP Views – Employee Portal

Self-service views for employees (DatabaseAssignment role='user').
Provides dashboard, attendance history, personal info, and QR scan result.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.utils import timezone

from erp.models import Employee, Attendance, LeaveRequest
from erp.decorators import employee_or_owner_required
from ._common import render, redirect, messages, reverse, get_user_company


def _get_employee_for_user(request):
    """Return the Employee record linked to the current user, or None."""
    user = request.user
    if hasattr(user, 'employee_profile') and user.employee_profile:
        return user.employee_profile
    # Fallback: try matching by email in the current tenant
    try:
        return Employee.objects.get(email=user.email, approval_status='approved')
    except Employee.DoesNotExist:
        return None


@employee_or_owner_required
def employee_portal(request):
    """Employee self-service dashboard."""
    employee = _get_employee_for_user(request)
    if not employee:
        messages.error(request, 'No employee profile found for your account.')
        from django.contrib.auth import logout
        logout(request)
        return redirect('tenants:login')

    today = date.today()
    month_start = today.replace(day=1)

    # This month's attendance
    month_attendances = Attendance.objects.filter(
        employee=employee,
        date__gte=month_start,
        date__lte=today,
    ).order_by('-date')

    total_present = month_attendances.filter(is_present=True).count()
    total_late = month_attendances.filter(is_late=True).count()
    total_days = (today - month_start).days + 1

    # Today's attendance
    today_attendance = Attendance.objects.filter(
        employee=employee, date=today,
    ).first()

    # Recent leave requests
    recent_leaves = LeaveRequest.objects.filter(
        employee=employee,
    ).order_by('-created_at')[:5]

    return render(request, 'erp/employee_portal/dashboard.html', {
        'employee': employee,
        'today_attendance': today_attendance,
        'month_attendances': month_attendances[:10],
        'total_present': total_present,
        'total_late': total_late,
        'total_days': total_days,
        'recent_leaves': recent_leaves,
    })


@employee_or_owner_required
def employee_portal_attendance(request):
    """Full attendance history for the logged-in employee."""
    employee = _get_employee_for_user(request)
    if not employee:
        messages.error(request, 'No employee profile found.')
        return redirect('tenants:home')

    today = date.today()
    start_date = request.GET.get('start_date', today.replace(day=1).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())

    attendances = Attendance.objects.filter(
        employee=employee,
        date__gte=start_date,
        date__lte=end_date,
    ).order_by('-date')

    stats = attendances.aggregate(
        present=Count('id', filter=Q(is_present=True)),
        late=Count('id', filter=Q(is_late=True)),
        absent=Count('id', filter=Q(is_present=False)),
    )

    return render(request, 'erp/employee_portal/my_attendance.html', {
        'employee': employee,
        'attendances': attendances,
        'stats': stats,
        'start_date': start_date,
        'end_date': end_date,
    })


@employee_or_owner_required
def employee_portal_profile(request):
    """View personal info (read-only for employees)."""
    employee = _get_employee_for_user(request)
    if not employee:
        messages.error(request, 'No employee profile found.')
        return redirect('tenants:home')

    return render(request, 'erp/employee_portal/profile.html', {
        'employee': employee,
    })


@employee_or_owner_required
def attendance_scan_result(request):
    """
    Process a scanned QR code and record attendance.

    Expects GET parameter ``qr`` with the signed payload from the kiosk.
    Performs check-in if no attendance exists for today, otherwise check-out.
    """
    from erp.models import AttendanceDevice

    employee = _get_employee_for_user(request)
    if not employee:
        messages.error(request, 'No employee profile found.')
        return render(request, 'erp/employee_portal/scan_result.html', {
            'success': False,
            'error': 'No employee profile linked to your account.',
        })

    qr_data = request.GET.get('qr', '')
    if not qr_data:
        return render(request, 'erp/employee_portal/scan_result.html', {
            'success': False,
            'error': 'No QR code data provided.',
        })

    # Validate QR payload
    try:
        device = AttendanceDevice.verify_qr_payload(qr_data, max_age=120)
    except ValueError as e:
        return render(request, 'erp/employee_portal/scan_result.html', {
            'success': False,
            'error': str(e),
        })

    # Ensure employee belongs to the same company as the device
    if employee.company_id != device.company_id:
        return render(request, 'erp/employee_portal/scan_result.html', {
            'success': False,
            'error': 'This device does not belong to your company.',
        })

    today = timezone.now().date()
    now_time = timezone.now().time()

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={
            'check_in': now_time,
            'is_present': True,
        },
    )

    action = 'check_in'

    if created:
        # New check-in
        # Check if late
        if device.work_start_time:
            from datetime import datetime, timedelta as td
            start_dt = datetime.combine(today, device.work_start_time)
            threshold_dt = start_dt + td(minutes=device.late_threshold_minutes)
            check_in_dt = datetime.combine(today, now_time)
            if check_in_dt > threshold_dt:
                attendance.is_late = True
                attendance.late_minutes = int(
                    (check_in_dt - start_dt).total_seconds() / 60
                )
                attendance.save(update_fields=['is_late', 'late_minutes'])
    else:
        # Already checked in today → record check-out
        action = 'check_out'
        attendance.check_out = now_time
        # Calculate hours worked
        if attendance.check_in:
            from datetime import datetime
            cin = datetime.combine(today, attendance.check_in)
            cout = datetime.combine(today, now_time)
            diff = (cout - cin).total_seconds() / 3600
            attendance.hours_worked = Decimal(str(round(diff, 2)))
            # Calculate overtime (hours over standard work day)
            if device.work_start_time and device.work_end_time:
                from datetime import datetime as dt
                standard = (
                    dt.combine(today, device.work_end_time)
                    - dt.combine(today, device.work_start_time)
                ).total_seconds() / 3600
                if diff > standard:
                    attendance.overtime_hours = Decimal(
                        str(round(diff - standard, 2))
                    )
        attendance.save()

    return render(request, 'erp/employee_portal/scan_result.html', {
        'success': True,
        'action': action,
        'attendance': attendance,
        'device': device,
        'employee': employee,
    })
