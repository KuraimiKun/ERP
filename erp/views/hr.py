"""
ERP Views -- HR

Employees, Departments, Attendance, Leave Requests, Payroll.
"""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.models import (
    Employee, Department, Attendance, LeaveRequest,
    Payroll, PayrollEarning, PayrollDeduction,
)
from erp.forms import (
    EmployeeForm, LeaveRequestForm, AttendanceForm, DepartmentForm,
    PayrollForm, PayrollEarningFormSet, PayrollDeductionFormSet,
)
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required, paginate_qs, apply_sorting,
)


# ── Employees ───────────────────────────────────────────────────────────────

@staff_member_required
def employee_list(request):
    company = get_user_company(request.user)
    employees = Employee.objects.filter(company=company).select_related('department')

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

    employees, current_sort, current_order = apply_sorting(
        request, employees,
        allowed_fields=['first_name', 'last_name', 'employee_id', 'employment_status', 'created_at'],
        default='first_name',
    )
    departments = Department.objects.filter(company=company, is_active=True)

    page_obj, query_string = paginate_qs(request, employees)

    return render(request, 'erp/employees/list.html', {
        'employees': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'departments': departments,
        'statuses': Employee.EmploymentStatus.choices,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def employee_detail(request, pk):
    company = get_user_company(request.user)
    employee = get_object_or_404(Employee, pk=pk, company=company)

    return render(request, 'erp/employees/detail.html', {
        'employee': employee,
        'documents': employee.documents.order_by('-created_at')[:50],
        'leave_requests': employee.leave_requests.order_by('-created_at')[:10],
        'attendances': employee.attendances.order_by('-date')[:30],
        'assigned_tasks': employee.assigned_tasks.order_by('-created_at')[:20],
    })


@staff_member_required
def employee_permissions_update(request, pk):
    """Save portal permission toggles for an employee (POST only)."""
    company = get_user_company(request.user)
    employee = get_object_or_404(Employee, pk=pk, company=company)

    if request.method != 'POST':
        return redirect('erp:employee_detail', pk=pk)

    perm_fields = [
        'portal_can_scan_qr', 'portal_can_view_attendance',
        'portal_can_manage_leaves', 'portal_can_view_payslips',
        'portal_can_edit_profile', 'portal_can_view_tasks',
        'portal_can_use_pos',
    ]
    for field in perm_fields:
        setattr(employee, field, field in request.POST)
    employee.save(update_fields=perm_fields)

    messages.success(request, f'Portal permissions updated for "{employee.full_name}".')
    return redirect('erp:employee_detail', pk=pk)


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

    departments, current_sort, current_order = apply_sorting(
        request, departments,
        allowed_fields=['name', 'created_at'],
        default='name',
    )
    page_obj, query_string = paginate_qs(request, departments)

    return render(request, 'erp/departments/list.html', {
        'departments': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'current_sort': current_sort,
        'current_order': current_order,
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
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def attendance_list(request):
    company = get_user_company(request.user)
    today = date.today()
    start_date = request.GET.get('start_date', today.replace(day=1).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())

    attendances = Attendance.objects.filter(
        employee__company=company,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee')

    attendances, current_sort, current_order = apply_sorting(
        request, attendances,
        allowed_fields=['date', 'employee__first_name'],
        default='-date',
    )
    page_obj, query_string = paginate_qs(request, attendances)

    return render(request, 'erp/attendance/list.html', {
        'attendances': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'start_date': start_date,
        'end_date': end_date,
        'current_sort': current_sort,
        'current_order': current_order,
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
    ).select_related('employee', 'leave_type', 'approved_by')

    status = request.GET.get('status')
    if status:
        leave_requests = leave_requests.filter(status=status)

    leave_requests, current_sort, current_order = apply_sorting(
        request, leave_requests,
        allowed_fields=['start_date', 'end_date', 'status', 'created_at'],
        default='-created_at',
    )
    page_obj, query_string = paginate_qs(request, leave_requests)

    return render(request, 'erp/leave_requests/list.html', {
        'leave_requests': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statuses': LeaveRequest.Status.choices,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def leave_request_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, company=company)
        if form.is_valid():
            form.save()
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
        if leave_request.status != 'pending':
            messages.error(request, 'يمكن الموافقة أو الرفض على الطلبات المعلقة فقط.')
            return redirect('erp:leave_request_detail', pk=pk)

        action = request.POST.get('action')
        notes = request.POST.get('notes', '')

        try:
            approver = request.user.employee_profile
        except Exception:
            approver = None

        if action == 'approve':
            leave_type = leave_request.leave_type
            days = leave_request.days_requested
            code = leave_type.code.lower()

            from django.db import transaction as _txn
            with _txn.atomic():
                employee = Employee.objects.select_for_update().get(pk=leave_request.employee_id)

                # Validate sufficient leave balance before approving
                if code == 'annual':
                    if employee.annual_leave_balance < days:
                        messages.error(
                            request,
                            f'رصيد الإجازة السنوية للموظف ({employee.annual_leave_balance} يوم) '
                            f'غير كافٍ للطلب ({days} يوم).'
                        )
                        return redirect('erp:leave_request_detail', pk=pk)
                elif code == 'sick':
                    if employee.sick_leave_balance < days:
                        messages.error(
                            request,
                            f'رصيد الإجازة المرضية للموظف ({employee.sick_leave_balance} يوم) '
                            f'غير كافٍ للطلب ({days} يوم).'
                        )
                        return redirect('erp:leave_request_detail', pk=pk)

                leave_request.status = 'approved'
                leave_request.approved_by = approver
                leave_request.approval_date = timezone.now()
                leave_request.approval_notes = notes
                leave_request.save()

                # Deduct from employee leave balance
                if code == 'annual':
                    employee.annual_leave_balance = max(employee.annual_leave_balance - days, 0)
                    employee.save(update_fields=['annual_leave_balance'])
                elif code == 'sick':
                    employee.sick_leave_balance = max(employee.sick_leave_balance - days, 0)
                    employee.save(update_fields=['sick_leave_balance'])

            messages.success(request, 'Leave request approved.')
        elif action == 'reject':
            was_approved = leave_request.status == 'approved'
            leave_request.status = 'rejected'
            leave_request.approved_by = approver
            leave_request.approval_date = timezone.now()
            leave_request.approval_notes = notes
            leave_request.save()

            # Restore leave balance if reversing a previously approved request
            if was_approved:
                employee = leave_request.employee
                days = leave_request.days_requested
                code = leave_request.leave_type.code.lower()
                if code == 'annual':
                    employee.annual_leave_balance += days
                    employee.save(update_fields=['annual_leave_balance'])
                elif code == 'sick':
                    employee.sick_leave_balance += days
                    employee.save(update_fields=['sick_leave_balance'])

            messages.warning(request, 'Leave request rejected.')

        return redirect('erp:leave_request_detail', pk=pk)

    return redirect('erp:leave_request_detail', pk=pk)


@staff_member_required
def leave_request_cancel(request, pk):
    """Cancel an approved or pending leave request and restore leave balance."""
    company = get_user_company(request.user)
    leave_request = get_object_or_404(LeaveRequest, pk=pk, employee__company=company)

    if request.method == 'POST':
        if leave_request.status not in ('pending', 'approved'):
            messages.error(request, 'لا يمكن إلغاء هذا الطلب.')
            return redirect('erp:leave_request_detail', pk=pk)

        was_approved = leave_request.status == 'approved'
        leave_request.status = 'cancelled'
        leave_request.save(update_fields=['status'])

        if was_approved:
            employee = leave_request.employee
            days = leave_request.days_requested
            code = leave_request.leave_type.code.lower()
            if code == 'annual':
                employee.annual_leave_balance += days
                employee.save(update_fields=['annual_leave_balance'])
            elif code == 'sick':
                employee.sick_leave_balance += days
                employee.save(update_fields=['sick_leave_balance'])
            messages.success(request, f'تم إلغاء إجازة {employee.full_name} واسترداد {days} يوم.')
        else:
            messages.success(request, 'تم إلغاء طلب الإجازة.')

    return redirect('erp:leave_request_detail', pk=pk)


# ── Payroll ─────────────────────────────────────────────────────────────────

@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def payroll_list(request):
    company = get_user_company(request.user)
    payrolls = Payroll.objects.filter(
        employee__company=company,
    ).select_related('employee', 'currency', 'journal_entry')

    status = request.GET.get('status')
    if status:
        payrolls = payrolls.filter(status=status)

    search = request.GET.get('search')
    if search:
        payrolls = payrolls.filter(
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search) |
            Q(employee__employee_id__icontains=search)
        )

    stats = payrolls.aggregate(
        total_count=Count('id'),
        total_net=Sum('net_salary'),
        total_gross=Sum('gross_salary'),
    )

    payrolls, current_sort, current_order = apply_sorting(
        request, payrolls,
        allowed_fields=['period_start', 'period_end', 'gross_salary', 'net_salary', 'status'],
        default='-period_start',
    )
    page_obj, query_string = paginate_qs(request, payrolls)

    return render(request, 'erp/payroll/list.html', {
        'payrolls': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'stats': stats,
        'selected_status': status or '',
        'statuses': Payroll.Status.choices,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def payroll_create(request):
    """Create payroll with inline earnings and deductions."""
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = PayrollForm(request.POST, company=company)
        earning_formset = PayrollEarningFormSet(request.POST, prefix='earnings')
        deduction_formset = PayrollDeductionFormSet(request.POST, prefix='deductions')

        if form.is_valid() and earning_formset.is_valid() and deduction_formset.is_valid():
            with transaction.atomic():
                payroll = form.save(commit=False)
                # Set basic_salary from employee for the default earning line
                payroll.save()

                earning_formset.instance = payroll
                earning_formset.save()

                deduction_formset.instance = payroll
                deduction_formset.save()

                payroll.calculate_totals()
                payroll.save()

            messages.success(request, 'Payroll created successfully.')
            return redirect('erp:payroll_detail', pk=payroll.pk)
    else:
        initial_data = {}
        employee_id = request.GET.get('employee')
        if employee_id:
            initial_data['employee'] = employee_id

        form = PayrollForm(company=company, initial=initial_data)

        # Pre-populate basic salary earning line from employee
        earning_initial = []
        if employee_id:
            try:
                emp = Employee.objects.get(pk=employee_id, company=company)
                earning_initial.append({
                    'earning_type': 'basic_salary',
                    'description': '',
                    'amount': emp.basic_salary,
                })
            except Employee.DoesNotExist:
                pass

        if not earning_initial:
            earning_initial.append({
                'earning_type': 'basic_salary',
                'description': '',
                'amount': Decimal('0'),
            })

        EarningFS = PayrollEarningFormSet
        earning_formset = EarningFS(
            prefix='earnings',
            initial=earning_initial,
            queryset=PayrollEarning.objects.none(),
        )
        deduction_formset = PayrollDeductionFormSet(
            prefix='deductions',
            queryset=PayrollDeduction.objects.none(),
        )

    return render(request, 'erp/payroll/form.html', {
        'form': form,
        'earning_formset': earning_formset,
        'deduction_formset': deduction_formset,
        'title': 'Create Payroll',
        'submit_text': 'Save Payroll',
        'earning_types': PayrollEarning.EarningType.choices,
        'deduction_types': PayrollDeduction.DeductionType.choices,
    })


@staff_member_required
def payroll_edit(request, pk):
    """Edit payroll with inline earnings and deductions."""
    company = get_user_company(request.user)
    payroll = get_object_or_404(Payroll, pk=pk, employee__company=company)

    if payroll.status in ('approved', 'paid'):
        messages.error(request, 'Cannot edit an approved or paid payroll.')
        return redirect('erp:payroll_detail', pk=pk)

    if request.method == 'POST':
        form = PayrollForm(request.POST, instance=payroll, company=company)
        earning_formset = PayrollEarningFormSet(
            request.POST, instance=payroll, prefix='earnings',
        )
        deduction_formset = PayrollDeductionFormSet(
            request.POST, instance=payroll, prefix='deductions',
        )

        if form.is_valid() and earning_formset.is_valid() and deduction_formset.is_valid():
            with transaction.atomic():
                payroll = form.save()
                earning_formset.save()
                deduction_formset.save()
                payroll.calculate_totals()
                payroll.save()

            messages.success(request, 'Payroll updated successfully.')
            return redirect('erp:payroll_detail', pk=payroll.pk)
    else:
        form = PayrollForm(instance=payroll, company=company)
        earning_formset = PayrollEarningFormSet(
            instance=payroll, prefix='earnings',
        )
        deduction_formset = PayrollDeductionFormSet(
            instance=payroll, prefix='deductions',
        )

    return render(request, 'erp/payroll/form.html', {
        'form': form,
        'payroll': payroll,
        'earning_formset': earning_formset,
        'deduction_formset': deduction_formset,
        'title': f'Edit Payroll: {payroll.employee.full_name}',
        'submit_text': 'Save Changes',
        'earning_types': PayrollEarning.EarningType.choices,
        'deduction_types': PayrollDeduction.DeductionType.choices,
    })


@staff_member_required
def payroll_detail(request, pk):
    company = get_user_company(request.user)
    payroll = get_object_or_404(
        Payroll, pk=pk, employee__company=company,
    )
    earnings = payroll.earning_lines.all()
    deductions = payroll.deduction_lines.all()

    return render(request, 'erp/payroll/detail.html', {
        'payroll': payroll,
        'earnings': earnings,
        'deductions': deductions,
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
            messages.success(request, 'Payroll calculated successfully.')

        elif action == 'approve':
            if payroll.status != 'calculated':
                messages.error(request, 'Payroll must be in Calculated status before it can be approved.')
                return redirect('erp:payroll_detail', pk=pk)
            payroll.status = Payroll.Status.APPROVED
            payroll.save()
            messages.success(request, 'Payroll approved.')

        elif action == 'pay':
            if payroll.status != 'approved':
                messages.error(request, 'Payroll must be approved first.')
                return redirect('erp:payroll_detail', pk=pk)

            payroll.status = Payroll.Status.PAID
            payroll.payment_date = timezone.now().date()
            payroll.save()

            # Create journal entry for the payroll
            try:
                je = payroll.create_journal_entry(user=request.user)
                messages.success(
                    request,
                    f'Salary disbursed. Journal entry {je.entry_number} created and posted.'
                )
            except ValueError as e:
                messages.warning(
                    request,
                    f'Salary disbursed but journal entry could not be created: {e}'
                )
            except Exception as e:
                messages.warning(
                    request,
                    f'Salary disbursed but journal entry failed: {e}'
                )

    return redirect('erp:payroll_detail', pk=pk)


@staff_member_required
def payroll_delete(request, pk):
    company = get_user_company(request.user)
    payroll = get_object_or_404(Payroll, pk=pk, employee__company=company)

    if request.method == 'POST':
        if payroll.status == 'paid':
            messages.error(request, 'Cannot delete a paid payroll.')
            return redirect('erp:payroll_detail', pk=pk)
        payroll.delete()
        messages.success(request, 'Payroll deleted.')
        return redirect('erp:payroll_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': payroll,
        'object_type': 'Payroll',
        'cancel_url': reverse('erp:payroll_detail', args=[pk]),
    })


@staff_member_required
def payroll_get_employee_salary(request):
    """AJAX endpoint: return employee basic_salary and currency_id."""
    from django.http import JsonResponse

    company = get_user_company(request.user)
    employee_id = request.GET.get('employee_id')
    if not employee_id:
        return JsonResponse({'error': 'No employee_id'}, status=400)

    try:
        emp = Employee.objects.get(pk=employee_id, company=company)
        return JsonResponse({
            'basic_salary': str(emp.basic_salary),
            'currency_id': emp.currency_id,
        })
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
