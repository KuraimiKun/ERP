"""
ERP Views – HR

Employees, Departments, Attendance, Leave Requests.
"""

from datetime import date

from django.db.models import Q
from django.utils import timezone

from erp.models import Employee, Department, Attendance, LeaveRequest, Payroll
from erp.forms import EmployeeForm, LeaveRequestForm, AttendanceForm, DepartmentForm, PayrollForm
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required,
)


# ── Employees ───────────────────────────────────────────────────────────────

@staff_member_required
def employee_list(request):
    company = get_user_company(request.user)
    employees = Employee.objects.filter(company=company).select_related('department').order_by('first_name')

    department = request.GET.get('department')
    if department:
        employees = employees.filter(department_id=department)

    status = request.GET.get('status')
    if status:
        employees = employees.filter(employment_status=status)

    search = request.GET.get('search')
    if search:
        employees = employees.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(employee_id__icontains=search)
        )

    departments = Department.objects.filter(company=company, is_active=True)

    return render(request, 'erp/employees/list.html', {
        'employees': employees,
        'departments': departments,
        'statuses': Employee.EmploymentStatus.choices,
    })


@staff_member_required
def employee_detail(request, pk):
    company = get_user_company(request.user)
    employee = get_object_or_404(Employee, pk=pk, company=company)

    return render(request, 'erp/employees/detail.html', {
        'employee': employee,
        'documents': employee.documents.order_by('-created_at'),
        'leave_requests': employee.leave_requests.order_by('-created_at')[:10],
        'attendances': employee.attendances.order_by('-date')[:30],
    })


@staff_member_required
def employee_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.company = company
            employee.save()
            messages.success(request, f'Employee "{employee.full_name}" created successfully.')
            return redirect('erp:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(company=company)

    return render(request, 'erp/employees/form.html', {
        'form': form,
        'title': 'Add Employee',
        'submit_text': 'Create Employee',
    })


@staff_member_required
def employee_edit(request, pk):
    company = get_user_company(request.user)
    employee = get_object_or_404(Employee, pk=pk, company=company)

    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Employee "{employee.full_name}" updated successfully.')
            return redirect('erp:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee, company=company)

    return render(request, 'erp/employees/form.html', {
        'form': form,
        'employee': employee,
        'title': f'Edit Employee: {employee.full_name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def employee_delete(request, pk):
    company = get_user_company(request.user)
    employee = get_object_or_404(Employee, pk=pk, company=company)

    if request.method == 'POST':
        name = employee.full_name
        employee.delete()
        messages.success(request, f'Employee "{name}" deleted successfully.')
        return redirect('erp:employee_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': employee,
        'object_type': 'Employee',
        'cancel_url': reverse('erp:employee_detail', args=[pk]),
    })


# ── Departments ─────────────────────────────────────────────────────────────

@staff_member_required
def department_list(request):
    company = get_user_company(request.user)
    departments = Department.objects.filter(company=company).select_related('parent', 'manager')

    return render(request, 'erp/departments/list.html', {
        'departments': departments.order_by('name'),
    })


@staff_member_required
def department_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = DepartmentForm(request.POST, company=company)
        if form.is_valid():
            department = form.save(commit=False)
            department.company = company
            department.save()
            messages.success(request, f'Department "{department.name}" created successfully.')
            return redirect('erp:department_list')
    else:
        form = DepartmentForm(company=company)

    return render(request, 'erp/departments/form.html', {
        'form': form,
        'title': 'Create Department',
        'submit_text': 'Create Department',
    })


@staff_member_required
def department_edit(request, pk):
    company = get_user_company(request.user)
    department = get_object_or_404(Department, pk=pk, company=company)

    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Department "{department.name}" updated successfully.')
            return redirect('erp:department_list')
    else:
        form = DepartmentForm(instance=department, company=company)

    return render(request, 'erp/departments/form.html', {
        'form': form,
        'department': department,
        'title': f'Edit Department: {department.name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def department_delete(request, pk):
    company = get_user_company(request.user)
    department = get_object_or_404(Department, pk=pk, company=company)

    if request.method == 'POST':
        name = department.name
        department.delete()
        messages.success(request, f'Department "{name}" deleted successfully.')
        return redirect('erp:department_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': department,
        'object_type': 'Department',
        'cancel_url': reverse('erp:department_list'),
    })


# ── Attendance ──────────────────────────────────────────────────────────────

@staff_member_required
def attendance_list(request):
    company = get_user_company(request.user)
    today = date.today()
    start_date = request.GET.get('start_date', today.replace(day=1).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())

    attendances = Attendance.objects.filter(
        employee__company=company,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee').order_by('-date', 'employee__first_name')

    return render(request, 'erp/attendance/list.html', {
        'attendances': attendances[:200],
        'start_date': start_date,
        'end_date': end_date,
    })


@staff_member_required
def attendance_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = AttendanceForm(request.POST, company=company)
        if form.is_valid():
            attendance = form.save()
            messages.success(request, f'Attendance recorded for {attendance.employee.full_name}.')
            return redirect('erp:attendance_list')
    else:
        form = AttendanceForm(company=company)

    return render(request, 'erp/attendance/form.html', {
        'form': form,
        'title': 'Record Attendance',
        'submit_text': 'Save Attendance',
    })


@staff_member_required
def attendance_edit(request, pk):
    company = get_user_company(request.user)
    attendance = get_object_or_404(Attendance, pk=pk, employee__company=company)

    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attendance updated successfully.')
            return redirect('erp:attendance_list')
    else:
        form = AttendanceForm(instance=attendance, company=company)

    return render(request, 'erp/attendance/form.html', {
        'form': form,
        'attendance': attendance,
        'title': f'Edit Attendance: {attendance.employee.full_name} - {attendance.date}',
        'submit_text': 'Save Changes',
    })


# ── Leave Requests ──────────────────────────────────────────────────────────

@staff_member_required
def leave_request_list(request):
    company = get_user_company(request.user)
    leave_requests = LeaveRequest.objects.filter(
        employee__company=company
    ).select_related('employee', 'leave_type', 'approved_by').order_by('-created_at')

    status = request.GET.get('status')
    if status:
        leave_requests = leave_requests.filter(status=status)

    return render(request, 'erp/leave_requests/list.html', {
        'leave_requests': leave_requests[:100],
        'statuses': LeaveRequest.Status.choices,
    })


@staff_member_required
def leave_request_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, company=company)
        if form.is_valid():
            leave_request = form.save()
            messages.success(request, 'Leave request submitted successfully.')
            return redirect('erp:leave_request_list')
    else:
        form = LeaveRequestForm(company=company)

    return render(request, 'erp/leave_requests/form.html', {
        'form': form,
        'title': 'Submit Leave Request',
        'submit_text': 'Submit Request',
    })


@staff_member_required
def leave_request_detail(request, pk):
    company = get_user_company(request.user)
    leave_request = get_object_or_404(LeaveRequest, pk=pk, employee__company=company)

    return render(request, 'erp/leave_requests/detail.html', {
        'leave_request': leave_request,
    })


@staff_member_required
def leave_request_approve(request, pk):
    company = get_user_company(request.user)
    leave_request = get_object_or_404(LeaveRequest, pk=pk, employee__company=company)

    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')

        try:
            approver = request.user.employee_profile
        except Exception:
            approver = None

        if action == 'approve':
            leave_request.status = 'approved'
            leave_request.approved_by = approver
            leave_request.approval_date = timezone.now()
            leave_request.approval_notes = notes
            leave_request.save()
            messages.success(request, 'Leave request approved.')
        elif action == 'reject':
            leave_request.status = 'rejected'
            leave_request.approved_by = approver
            leave_request.approval_date = timezone.now()
            leave_request.approval_notes = notes
            leave_request.save()
            messages.warning(request, 'Leave request rejected.')

        return redirect('erp:leave_request_detail', pk=pk)

    return redirect('erp:leave_request_detail', pk=pk)


# ── Payroll ─────────────────────────────────────────────────────────────────

@staff_member_required
def payroll_list(request):
    company = get_user_company(request.user)
    payrolls = Payroll.objects.filter(
        employee__company=company,
    ).select_related('employee', 'currency').order_by('-period_start')

    status = request.GET.get('status')
    if status:
        payrolls = payrolls.filter(status=status)

    search = request.GET.get('search')
    if search:
        from django.db.models import Q
        payrolls = payrolls.filter(
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search) |
            Q(employee__employee_id__icontains=search)
        )

    from django.db.models import Sum, Count
    stats = payrolls.aggregate(
        total_count=Count('id'),
        total_net=Sum('net_salary'),
        total_gross=Sum('gross_salary'),
    )

    return render(request, 'erp/payroll/list.html', {
        'payrolls': payrolls[:100],
        'stats': stats,
        'selected_status': status or '',
        'statuses': Payroll.Status.choices,
    })


@staff_member_required
def payroll_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = PayrollForm(request.POST, company=company)
        if form.is_valid():
            payroll = form.save(commit=False)
            payroll.calculate_totals()
            payroll.save()
            messages.success(request, f'تم إنشاء كشف الراتب بنجاح.')
            return redirect('erp:payroll_detail', pk=payroll.pk)
    else:
        form = PayrollForm(company=company)
        employee_id = request.GET.get('employee')
        if employee_id:
            form = PayrollForm(company=company, initial={'employee': employee_id})

    return render(request, 'erp/payroll/form.html', {
        'form': form,
        'title': 'إنشاء كشف راتب',
        'submit_text': 'حفظ',
    })


@staff_member_required
def payroll_detail(request, pk):
    company = get_user_company(request.user)
    payroll = get_object_or_404(Payroll, pk=pk, employee__company=company)

    return render(request, 'erp/payroll/detail.html', {
        'payroll': payroll,
    })


@staff_member_required
def payroll_approve(request, pk):
    company = get_user_company(request.user)
    payroll = get_object_or_404(Payroll, pk=pk, employee__company=company)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'calculate':
            payroll.calculate_totals()
            payroll.status = Payroll.Status.CALCULATED
            payroll.save()
            messages.success(request, 'تم احتساب الراتب بنجاح.')
        elif action == 'approve':
            if payroll.status not in ('draft', 'calculated'):
                messages.error(request, 'لا يمكن اعتماد كشف الراتب بحالته الحالية.')
                return redirect('erp:payroll_detail', pk=pk)
            payroll.calculate_totals()
            payroll.status = Payroll.Status.APPROVED
            payroll.save()
            messages.success(request, 'تم اعتماد كشف الراتب.')
        elif action == 'pay':
            if payroll.status != 'approved':
                messages.error(request, 'يجب اعتماد كشف الراتب أولاً.')
                return redirect('erp:payroll_detail', pk=pk)
            payroll.status = Payroll.Status.PAID
            payroll.payment_date = timezone.now().date()
            payroll.save()
            messages.success(request, 'تم صرف الراتب.')

    return redirect('erp:payroll_detail', pk=pk)


@staff_member_required
def payroll_delete(request, pk):
    company = get_user_company(request.user)
    payroll = get_object_or_404(Payroll, pk=pk, employee__company=company)

    if request.method == 'POST':
        if payroll.status in ('paid',):
            messages.error(request, 'لا يمكن حذف كشف راتب مصروف.')
            return redirect('erp:payroll_detail', pk=pk)
        payroll.delete()
        messages.success(request, 'تم حذف كشف الراتب.')
        return redirect('erp:payroll_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': payroll,
        'object_type': 'كشف راتب',
        'cancel_url': reverse('erp:payroll_detail', args=[pk]),
    })
