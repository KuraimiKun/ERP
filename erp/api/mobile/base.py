"""Shared helpers for the employee mobile API."""

from rest_framework.response import Response

from erp.models import Employee


def _get_employee(user):
    """Return the Employee record linked to ``user``, or ``None``."""
    if hasattr(user, 'employee_profile') and user.employee_profile:
        emp = user.employee_profile
    else:
        try:
            emp = Employee.objects.get(email=user.email, approval_status='approved')
        except Employee.DoesNotExist:
            return None

    # Retroactively assign company if missing (happens when employee registered
    # before a Company record existed in the tenant DB).
    if emp.company_id is None:
        from erp.models import Company
        company = Company.objects.first()
        if company:
            emp.company = company
            emp.save(update_fields=['company'])

    return emp


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
