"""
ERP Views – Employee Portal

Self-service views for employees (DatabaseAssignment role='user').
Provides dashboard, attendance history, leave requests, payslips,
QR scanner, personal profile, and password change.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django import forms as django_forms
from django.contrib.auth import update_session_auth_hash
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.views.decorators.http import require_POST

from erp.models import (
    Employee,
    Attendance,
    LeaveRequest,
    LeaveType,
    Payroll,
    PayrollEarning,
    PayrollDeduction,
    AttendanceDevice,
    Task,
    TaskComment,
)
from erp.decorators import employee_or_owner_required, portal_permission_required
from ._common import render, redirect, messages


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _get_employee_for_user(request):
    """Return the Employee record linked to the current user, or None."""
    user = request.user
    if hasattr(user, "employee_profile") and user.employee_profile:
        return user.employee_profile
    try:
        return Employee.objects.get(email=user.email, approval_status="approved")
    except Employee.DoesNotExist:
        return None


def _portal_context(employee):
    """Common context dict used by every portal view."""
    pending_leaves = LeaveRequest.objects.filter(
        employee=employee,
        status="pending",
    ).count()
    return {"employee": employee, "pending_leave_count": pending_leaves}


def _no_employee(request):
    """Standard response when no employee profile is linked."""
    messages.error(request, "No employee profile found for your account.")
    from django.contrib.auth import logout

    logout(request)
    return redirect("tenants:login")


# ═══════════════════════════════════════════════════════════════════════════
# Portal-specific forms (thin, no admin mixins)
# ═══════════════════════════════════════════════════════════════════════════


class _PortalLeaveForm(django_forms.ModelForm):
    """Simplified leave request form for the employee portal."""

    class Meta:
        model = LeaveRequest
        fields = ["leave_type", "start_date", "end_date", "reason"]
        widgets = {
            "start_date": django_forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": django_forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "reason": django_forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "leave_type": django_forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        self.fields["leave_type"].queryset = LeaveType.objects.filter(is_active=True)

    def clean(self):
        cd = super().clean()
        start = cd.get("start_date")
        end = cd.get("end_date")
        if start and end:
            if end < start:
                raise django_forms.ValidationError("End date cannot be before start date.")
            # Check for overlapping non-cancelled/rejected leave requests
            if self.employee:
                qs = LeaveRequest.objects.filter(
                    employee=self.employee,
                    status__in=("pending", "approved"),
                    start_date__lte=end,
                    end_date__gte=start,
                )
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise django_forms.ValidationError(
                        "You already have a leave request that overlaps with these dates."
                    )
        return cd


class _PortalProfileForm(django_forms.ModelForm):
    """Editable personal fields an employee can change themselves."""

    class Meta:
        model = Employee
        fields = [
            "phone",
            "emergency_contact_name",
            "emergency_contact_phone",
            "address",
            "city",
            "country",
        ]
        widgets = {
            "phone": django_forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_name": django_forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_phone": django_forms.TextInput(attrs={"class": "form-control"}),
            "address": django_forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "city": django_forms.TextInput(attrs={"class": "form-control"}),
            "country": django_forms.TextInput(attrs={"class": "form-control"}),
        }


class _PasswordChangeForm(django_forms.Form):
    """Simple password change form."""

    current_password = django_forms.CharField(
        widget=django_forms.PasswordInput(attrs={"class": "form-control"}),
    )
    new_password = django_forms.CharField(
        widget=django_forms.PasswordInput(attrs={"class": "form-control"}),
        min_length=8,
    )
    confirm_password = django_forms.CharField(
        widget=django_forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        pwd = self.cleaned_data["current_password"]
        if not self.user.check_password(pwd):
            raise django_forms.ValidationError("Current password is incorrect.")
        return pwd

    def clean(self):
        cd = super().clean()
        if cd.get("new_password") != cd.get("confirm_password"):
            raise django_forms.ValidationError("New passwords do not match.")
        return cd


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
def employee_portal(request):
    """Employee self-service dashboard."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    today = date.today()
    month_start = today.replace(day=1)

    month_attendances = Attendance.objects.filter(
        employee=employee,
        date__gte=month_start,
        date__lte=today,
    ).order_by("-date")

    total_present = month_attendances.filter(is_present=True).count()
    total_late = month_attendances.filter(is_late=True).count()
    total_days = (today - month_start).days + 1

    today_attendance = Attendance.objects.filter(
        employee=employee,
        date=today,
    ).first()

    recent_leaves = LeaveRequest.objects.filter(
        employee=employee,
    ).order_by("-created_at")[:5]

    recent_payrolls = Payroll.objects.filter(
        employee=employee,
        status__in=["approved", "paid"],
    ).order_by("-period_end")[:3]

    ctx = _portal_context(employee)
    ctx.update(
        {
            "today_attendance": today_attendance,
            "month_attendances": month_attendances[:10],
            "total_present": total_present,
            "total_late": total_late,
            "total_absent": total_days - total_present,
            "total_days": total_days,
            "recent_leaves": recent_leaves,
            "recent_payrolls": recent_payrolls,
        }
    )
    return render(request, "erp/employee_portal/dashboard.html", ctx)


# ═══════════════════════════════════════════════════════════════════════════
# QR Scanner
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
@portal_permission_required("portal_can_scan_qr")
def portal_qr_scanner(request):
    """Page with camera-based QR code scanner."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    ctx = _portal_context(employee)
    return render(request, "erp/employee_portal/qr_scanner.html", ctx)


# ═══════════════════════════════════════════════════════════════════════════
# Attendance
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
@portal_permission_required("portal_can_view_attendance")
def employee_portal_attendance(request):
    """Full attendance history for the logged-in employee."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    today = date.today()
    start_date = request.GET.get("start_date", today.replace(day=1).isoformat())
    end_date = request.GET.get("end_date", today.isoformat())

    attendances = Attendance.objects.filter(
        employee=employee,
        date__gte=start_date,
        date__lte=end_date,
    ).order_by("-date")

    stats = attendances.aggregate(
        present=Count("id", filter=Q(is_present=True)),
        late=Count("id", filter=Q(is_late=True)),
        absent=Count("id", filter=Q(is_present=False)),
    )

    ctx = _portal_context(employee)
    ctx.update(
        {
            "attendances": attendances,
            "stats": stats,
            "start_date": start_date,
            "end_date": end_date,
        }
    )
    return render(request, "erp/employee_portal/my_attendance.html", ctx)


# ═══════════════════════════════════════════════════════════════════════════
# QR Scan Processing
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
@portal_permission_required("portal_can_scan_qr")
def attendance_scan_result(request):
    """
    Process a scanned QR code and record attendance.

    Expects GET parameter ``qr`` with the signed payload from the kiosk.
    Performs check-in if no attendance exists for today, otherwise check-out.
    """
    employee = _get_employee_for_user(request)
    if not employee:
        return render(
            request,
            "erp/employee_portal/scan_result.html",
            {
                "success": False,
                "error": "No employee profile linked to your account.",
            },
        )

    qr_data = request.GET.get("qr", "")
    if not qr_data:
        return render(
            request,
            "erp/employee_portal/scan_result.html",
            {
                "success": False,
                "error": "No QR code data provided.",
            },
        )

    try:
        device = AttendanceDevice.verify_qr_payload(qr_data, max_age=120)
    except ValueError as e:
        return render(
            request,
            "erp/employee_portal/scan_result.html",
            {
                "success": False,
                "error": str(e),
            },
        )

    if employee.company_id != device.company_id:
        return render(
            request,
            "erp/employee_portal/scan_result.html",
            {
                "success": False,
                "error": "This device does not belong to your company.",
            },
        )

    today = timezone.now().date()
    now_time = timezone.now().time()

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={"check_in": now_time, "is_present": True},
    )

    action = "check_in"

    if created:
        if device.work_start_time:
            start_dt = datetime.combine(today, device.work_start_time)
            threshold_dt = start_dt + timedelta(minutes=device.late_threshold_minutes)
            check_in_dt = datetime.combine(today, now_time)
            if check_in_dt > threshold_dt:
                attendance.is_late = True
                attendance.late_minutes = int((check_in_dt - start_dt).total_seconds() / 60)
                attendance.save(update_fields=["is_late", "late_minutes"])
    else:
        action = "check_out"
        attendance.check_out = now_time
        if attendance.check_in:
            cin = datetime.combine(today, attendance.check_in)
            cout = datetime.combine(today, now_time)
            diff = (cout - cin).total_seconds() / 3600
            attendance.hours_worked = Decimal(str(round(diff, 2)))
            if device.work_start_time and device.work_end_time:
                standard = (
                    datetime.combine(today, device.work_end_time) - datetime.combine(today, device.work_start_time)
                ).total_seconds() / 3600
                if diff > standard:
                    attendance.overtime_hours = Decimal(str(round(diff - standard, 2)))
        attendance.save()

    ctx = _portal_context(employee)
    ctx.update(
        {
            "success": True,
            "action": action,
            "attendance": attendance,
            "device": device,
        }
    )
    return render(request, "erp/employee_portal/scan_result.html", ctx)


# ═══════════════════════════════════════════════════════════════════════════
# Leave Requests
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
@portal_permission_required("portal_can_manage_leaves")
def portal_leave_list(request):
    """List all leave requests for the logged-in employee."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    status_filter = request.GET.get("status", "")
    leaves = LeaveRequest.objects.filter(employee=employee).order_by("-created_at")
    if status_filter:
        leaves = leaves.filter(status=status_filter)

    # Remaining leave balance per type
    leave_balances = []
    for lt in LeaveType.objects.filter(is_active=True):
        used = (
            LeaveRequest.objects.filter(
                employee=employee,
                leave_type=lt,
                status__in=["pending", "approved"],
                start_date__year=date.today().year,
            ).aggregate(total=Sum("days_requested"))["total"]
            or 0
        )
        leave_balances.append(
            {
                "type": lt,
                "allowed": lt.days_allowed,
                "used": used,
                "remaining": max(lt.days_allowed - used, 0),
            }
        )

    ctx = _portal_context(employee)
    ctx.update(
        {
            "leaves": leaves,
            "status_filter": status_filter,
            "leave_balances": leave_balances,
        }
    )
    return render(request, "erp/employee_portal/leave_list.html", ctx)


@employee_or_owner_required
@portal_permission_required("portal_can_manage_leaves")
def portal_leave_create(request):
    """Submit a new leave request."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    if request.method == "POST":
        form = _PortalLeaveForm(request.POST, employee=employee)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.employee = employee
            # Auto-calculate days
            delta = (leave.end_date - leave.start_date).days + 1
            leave.days_requested = delta
            leave.status = "pending"
            leave.save()
            messages.success(request, "Leave request submitted successfully.")
            return redirect("erp:employee_portal_leave_list")
    else:
        form = _PortalLeaveForm(employee=employee)

    ctx = _portal_context(employee)
    ctx["form"] = form
    return render(request, "erp/employee_portal/leave_form.html", ctx)


@employee_or_owner_required
@portal_permission_required("portal_can_manage_leaves")
@require_POST
def portal_leave_cancel(request, pk):
    """Cancel a pending leave request."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    try:
        leave = LeaveRequest.objects.get(pk=pk, employee=employee)
    except LeaveRequest.DoesNotExist:
        messages.error(request, "Leave request not found.")
        return redirect("erp:employee_portal_leave_list")

    if leave.status != "pending":
        messages.error(request, "Only pending requests can be cancelled.")
    else:
        leave.status = "cancelled"
        leave.save(update_fields=["status"])
        messages.success(request, "Leave request cancelled.")

    return redirect("erp:employee_portal_leave_list")


# ═══════════════════════════════════════════════════════════════════════════
# Payslips
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
@portal_permission_required("portal_can_view_payslips")
def portal_payslip_list(request):
    """List payslips visible to the employee (approved/paid only)."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    payrolls = Payroll.objects.filter(
        employee=employee,
        status__in=["approved", "paid"],
    ).order_by("-period_end")

    ctx = _portal_context(employee)
    ctx["payrolls"] = payrolls
    return render(request, "erp/employee_portal/payslip_list.html", ctx)


@employee_or_owner_required
@portal_permission_required("portal_can_view_payslips")
def portal_payslip_detail(request, pk):
    """View a single payslip with full earnings/deductions breakdown."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    try:
        payroll = Payroll.objects.get(
            pk=pk,
            employee=employee,
            status__in=["approved", "paid"],
        )
    except Payroll.DoesNotExist:
        messages.error(request, "Payslip not found.")
        return redirect("erp:employee_portal_payslip_list")

    earnings = PayrollEarning.objects.filter(payroll=payroll)
    deductions = PayrollDeduction.objects.filter(payroll=payroll)

    ctx = _portal_context(employee)
    ctx.update(
        {
            "payroll": payroll,
            "earnings": earnings,
            "deductions": deductions,
        }
    )
    return render(request, "erp/employee_portal/payslip_detail.html", ctx)


# ═══════════════════════════════════════════════════════════════════════════
# Profile
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
def employee_portal_profile(request):
    """View personal information (read-only overview)."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    ctx = _portal_context(employee)
    return render(request, "erp/employee_portal/profile.html", ctx)


@employee_or_owner_required
@portal_permission_required("portal_can_edit_profile")
def portal_profile_edit(request):
    """Edit personal information (limited fields)."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    if request.method == "POST":
        form = _PortalProfileForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("erp:employee_portal_profile")
    else:
        form = _PortalProfileForm(instance=employee)

    ctx = _portal_context(employee)
    ctx["form"] = form
    return render(request, "erp/employee_portal/profile_edit.html", ctx)


# ═══════════════════════════════════════════════════════════════════════════
# Password Change
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
def portal_change_password(request):
    """Change the logged-in user's password."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    if request.method == "POST":
        form = _PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password changed successfully.")
            return redirect("erp:employee_portal")
    else:
        form = _PasswordChangeForm(request.user)

    ctx = _portal_context(employee)
    ctx["form"] = form
    return render(request, "erp/employee_portal/change_password.html", ctx)


# ═══════════════════════════════════════════════════════════════════════════
# Tasks
# ═══════════════════════════════════════════════════════════════════════════


@employee_or_owner_required
@portal_permission_required("portal_can_view_tasks")
def portal_task_list(request):
    """List tasks assigned to the logged-in employee."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    status_filter = request.GET.get("status", "")
    tasks = Task.objects.filter(assigned_to=employee).order_by("-created_at")
    if status_filter:
        tasks = tasks.filter(status=status_filter)

    # Summary counts
    task_counts = {
        "total": tasks.count(),
        "todo": tasks.filter(status="todo").count(),
        "in_progress": tasks.filter(status="in_progress").count(),
        "completed": tasks.filter(status="completed").count(),
    }

    ctx = _portal_context(employee)
    ctx.update(
        {
            "tasks": tasks,
            "status_filter": status_filter,
            "task_counts": task_counts,
            "statuses": Task.Status.choices,
        }
    )
    return render(request, "erp/employee_portal/task_list.html", ctx)


@employee_or_owner_required
@portal_permission_required("portal_can_view_tasks")
def portal_task_detail(request, pk):
    """View a single task with comments."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    try:
        task = Task.objects.get(pk=pk, assigned_to=employee)
    except Task.DoesNotExist:
        messages.error(request, "Task not found.")
        return redirect("erp:employee_portal_task_list")

    comments = task.comments.select_related("author").order_by("created_at")

    # Handle new comment
    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content:
            TaskComment.objects.create(
                task=task,
                author=request.user,
                content=content,
            )
            messages.success(request, "Comment added.")
            return redirect("erp:employee_portal_task_detail", pk=pk)

    # Handle status update via GET param (quick action)
    new_status = request.GET.get("set_status", "")
    if new_status in [s[0] for s in Task.Status.choices]:
        task.status = new_status
        if new_status == "completed":
            task.completed_date = timezone.now()
        task.save(update_fields=["status", "completed_date"])
        messages.success(request, f'Task status updated to "{task.get_status_display()}".')
        return redirect("erp:employee_portal_task_detail", pk=pk)

    ctx = _portal_context(employee)
    ctx.update(
        {
            "task": task,
            "comments": comments,
            "statuses": Task.Status.choices,
        }
    )
    return render(request, "erp/employee_portal/task_detail.html", ctx)
