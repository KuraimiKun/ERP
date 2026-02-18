"""
ERP Forms - HR

Forms for Employee, LeaveRequest, Attendance.
"""

from django import forms
from django.contrib.auth import get_user_model

from erp.models import Employee, LeaveRequest, Attendance
from .mixins import BootstrapFormMixin, CompanyFilterMixin

User = get_user_model()


class EmployeeForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Employee model."""

    class Meta:
        model = Employee
        fields = [
            'user', 'employee_id', 'first_name', 'last_name', 'first_name_ar',
            'last_name_ar', 'gender', 'date_of_birth', 'nationality',
            'email', 'phone', 'emergency_contact_name', 'emergency_contact_phone',
            'address', 'city', 'country', 'national_id', 'passport_number',
            'passport_expiry', 'photo', 'department', 'branch', 'job_title',
            'employment_type', 'employment_status', 'hire_date', 'reports_to',
            'basic_salary', 'currency', 'bank_name', 'bank_account', 'iban'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'passport_expiry': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users who don't already have employee profiles
        if not self.instance.pk:
            existing_employee_users = Employee.objects.exclude(user__isnull=True).values_list('user_id', flat=True)
            self.fields['user'].queryset = User.objects.exclude(id__in=existing_employee_users)


class LeaveRequestForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for LeaveRequest model."""

    class Meta:
        model = LeaveRequest
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }


class AttendanceForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Attendance model."""

    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'check_in', 'check_out', 'is_present', 'is_late', 'late_minutes', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'check_in': forms.TimeInput(attrs={'type': 'time'}),
            'check_out': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
