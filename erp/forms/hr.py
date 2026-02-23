"""
ERP Forms - HR

Forms for Employee, LeaveRequest, Attendance.
"""

from django import forms
from django.contrib.auth import get_user_model

from erp.models import Employee, LeaveRequest, Attendance, Payroll
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
        fields = ['employee', 'leave_type', 'start_date', 'end_date', 'days_requested', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        days_requested = cleaned_data.get('days_requested')

        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError('End date cannot be before start date.')
            # Auto-calculate days if not provided
            if not days_requested:
                delta = (end_date - start_date).days + 1
                cleaned_data['days_requested'] = delta

        return cleaned_data


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


class PayrollForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Payroll model."""

    class Meta:
        model = Payroll
        fields = [
            'employee', 'period_start', 'period_end', 'currency',
            'basic_salary', 'housing_allowance', 'transport_allowance',
            'other_allowances', 'overtime_amount', 'bonus',
            'absence_deduction', 'late_deduction', 'loan_deduction',
            'social_insurance', 'tax_deduction', 'other_deductions',
            'notes',
        ]
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.company:
            self.fields['employee'].queryset = Employee.objects.filter(
                company=self.company, employment_status='active',
            ).order_by('first_name')
        # Pre-fill basic salary from employee
        if not self.instance.pk:
            employee_id = self.data.get('employee') or self.initial.get('employee')
            if employee_id:
                try:
                    emp = Employee.objects.get(pk=employee_id)
                    if not self.data.get('basic_salary'):
                        self.initial['basic_salary'] = emp.basic_salary
                    if not self.data.get('currency'):
                        self.initial['currency'] = emp.currency_id
                except Employee.DoesNotExist:
                    pass
