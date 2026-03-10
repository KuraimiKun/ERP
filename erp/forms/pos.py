"""
ERP Forms - POS (Point of Sale)

Forms for POS Terminal management in the admin panel.
"""

from django import forms

from erp.models import POSTerminal
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class POSTerminalForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    class Meta:
        model = POSTerminal
        fields = [
            'code', 'name', 'name_ar', 'location',
            'warehouse', 'default_customer',
            'allowed_employees',
            'receipt_header', 'receipt_footer',
            'is_active',
        ]
        widgets = {
            'receipt_header': forms.Textarea(attrs={'rows': 2}),
            'receipt_footer': forms.Textarea(attrs={'rows': 2}),
            'allowed_employees': forms.CheckboxSelectMultiple,
        }
