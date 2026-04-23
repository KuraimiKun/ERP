"""
ERP Forms - HR

Forms for Employee, LeaveRequest, Attendance, Payroll with
editable Earnings/Deductions line items.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from erp.models import (
    Employee,
    LeaveRequest,
    Attendance,
    Payroll,
    PayrollEarning,
    PayrollDeduction,
    AttendanceDevice,
)
from .mixins import BootstrapFormMixin, CompanyFilterMixin

User = get_user_model()


class EmployeeForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Employee model."""

    class Meta:
        model = Employee
        fields = [
            "user",
            "employee_id",
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "gender",
            "date_of_birth",
            "nationality",
            "email",
            "phone",
            "emergency_contact_name",
            "emergency_contact_phone",
            "address",
            "city",
            "country",
            "national_id",
            "passport_number",
            "passport_expiry",
            "photo",
            "department",
            "branch",
            "job_title",
            "employment_type",
            "employment_status",
            "hire_date",
            "reports_to",
            "basic_salary",
            "currency",
            "bank_name",
            "bank_account",
            "iban",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "passport_expiry": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users who don't already have employee profiles
        if not self.instance.pk:
            existing_employee_users = Employee.objects.exclude(user__isnull=True).values_list("user_id", flat=True)
            self.fields["user"].queryset = User.objects.exclude(id__in=existing_employee_users)


class LeaveRequestForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for LeaveRequest model."""

    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "start_date", "end_date", "days_requested", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        days_requested = cleaned_data.get("days_requested")

        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError("End date cannot be before start date.")
            # Auto-calculate days if not provided
            if not days_requested:
                delta = (end_date - start_date).days + 1
                cleaned_data["days_requested"] = delta

        return cleaned_data


class AttendanceForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Attendance model."""

    class Meta:
        model = Attendance
        fields = ["employee", "date", "check_in", "check_out", "is_present", "is_late", "late_minutes", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "check_in": forms.TimeInput(attrs={"type": "time"}),
            "check_out": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class PayrollForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Payroll header (employee, period, currency, notes)."""

    class Meta:
        model = Payroll
        fields = [
            "employee",
            "period_start",
            "period_end",
            "currency",
            "notes",
        ]
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.company:
            self.fields["employee"].queryset = Employee.objects.filter(
                company=self.company,
                employment_status="active",
            ).order_by("first_name")
        # Pre-fill currency from employee
        if not self.instance.pk:
            employee_id = self.data.get("employee") or self.initial.get("employee")
            if employee_id:
                try:
                    emp = Employee.objects.get(pk=employee_id)
                    if not self.data.get("currency"):
                        self.initial["currency"] = emp.currency_id
                except Employee.DoesNotExist:
                    pass


# ── Earning line form ───────────────────────────────────────────


class PayrollEarningForm(BootstrapFormMixin, forms.ModelForm):
    """Form for a single earnings line item."""

    class Meta:
        model = PayrollEarning
        fields = ["earning_type", "description", "amount"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "Description (optional)"}),
            "amount": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "class": "text-end earning-amount",
                }
            ),
        }


PayrollEarningFormSet = inlineformset_factory(
    Payroll,
    PayrollEarning,
    form=PayrollEarningForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# ── Deduction line form ────────────────────────────────────────


class PayrollDeductionForm(BootstrapFormMixin, forms.ModelForm):
    """Form for a single deductions line item."""

    class Meta:
        model = PayrollDeduction
        fields = ["deduction_type", "description", "amount"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "Description (optional)"}),
            "amount": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "class": "text-end deduction-amount",
                }
            ),
        }


PayrollDeductionFormSet = inlineformset_factory(
    Payroll,
    PayrollDeduction,
    form=PayrollDeductionForm,
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


# ── Attendance Device form ─────────────────────────────────────


class AttendanceDeviceForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for registering / editing an attendance kiosk device."""

    class Meta:
        model = AttendanceDevice
        fields = [
            "name",
            "location",
            "work_start_time",
            "work_end_time",
            "late_threshold_minutes",
            "qr_refresh_seconds",
            "is_active",
        ]
        widgets = {
            "work_start_time": forms.TimeInput(attrs={"type": "time"}),
            "work_end_time": forms.TimeInput(attrs={"type": "time"}),
        }
