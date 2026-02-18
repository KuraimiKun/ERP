"""
Selectors – HR

Employees, Departments, Attendance, Leave Requests.
"""

from datetime import date

from django.db.models import Q

from erp.models import Employee, Department, Attendance, LeaveRequest

__all__ = [
    'get_employee_list',
    'get_employee_detail_context',
    'get_department_list',
    'get_attendance_list',
    'get_leave_request_list',
]


def get_employee_list(company, *, department=None, status=None, search=None):
    qs = (
        Employee.objects.filter(company=company)
        .select_related('department')
        .order_by('first_name')
    )
    if department:
        qs = qs.filter(department_id=department)
    if status:
        qs = qs.filter(employment_status=status)
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(employee_id__icontains=search)
        )
    return qs


def get_employee_detail_context(employee):
    return {
        'documents': employee.documents.order_by('-created_at'),
        'leave_requests': employee.leave_requests.order_by('-created_at')[:10],
        'attendances': employee.attendances.order_by('-date')[:30],
    }


def get_department_list(company):
    return (
        Department.objects.filter(company=company)
        .select_related('parent', 'manager')
        .order_by('name')
    )


def get_attendance_list(company, *, start_date=None, end_date=None, limit=200):
    today = date.today()
    start_date = start_date or today.replace(day=1).isoformat()
    end_date = end_date or today.isoformat()

    qs = (
        Attendance.objects.filter(
            employee__company=company,
            date__gte=start_date,
            date__lte=end_date,
        )
        .select_related('employee')
        .order_by('-date', 'employee__first_name')
    )
    return qs[:limit]


def get_leave_request_list(company, *, status=None, limit=100):
    qs = (
        LeaveRequest.objects.filter(employee__company=company)
        .select_related('employee', 'leave_type', 'approved_by')
        .order_by('-created_at')
    )
    if status:
        qs = qs.filter(status=status)
    return qs[:limit]
