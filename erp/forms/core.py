"""
ERP Forms - Core

Forms for Company, Department, Branch, Currency, FiscalYear.
"""

from django import forms

from erp.models import Company, Currency, Department, Branch, FiscalYear
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class CompanyForm(BootstrapFormMixin, forms.ModelForm):
    """Form for Company model."""

    class Meta:
        model = Company
        fields = [
            "name",
            "name_ar",
            "legal_name",
            "tax_number",
            "commercial_register",
            "license_number",
            "email",
            "phone",
            "fax",
            "website",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "logo",
            "base_currency",
            "fiscal_year_start",
            "bank_name",
            "bank_account",
            "iban",
            "swift_code",
            "ai_enabled",
            "openai_api_key",
            "openai_model",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "openai_api_key": forms.PasswordInput(
                attrs={
                    "placeholder": "sk-…",
                    "autocomplete": "off",
                }
            ),
        }


class DepartmentForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Department model."""

    class Meta:
        model = Department
        fields = ["name", "name_ar", "code", "description", "parent", "manager", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class BranchForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Branch model."""

    class Meta:
        model = Branch
        fields = [
            "name",
            "name_ar",
            "code",
            "address",
            "city",
            "country",
            "phone",
            "email",
            "manager",
            "is_headquarters",
            "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }


class CurrencyForm(BootstrapFormMixin, forms.ModelForm):
    """Form for Currency model."""

    class Meta:
        model = Currency
        fields = ["code", "name", "name_ar", "symbol", "exchange_rate", "is_active"]


class FiscalYearForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for FiscalYear model."""

    class Meta:
        model = FiscalYear
        fields = ["name", "start_date", "end_date", "is_current", "is_closed"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
