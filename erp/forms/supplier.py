"""
ERP Forms - Supplier

Forms for Supplier, SupplierContact, PurchaseOrder, PurchaseOrderLine.
"""

from django import forms

from erp.models import Supplier, SupplierContact, PurchaseOrder, PurchaseOrderLine
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class SupplierForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Supplier model."""

    class Meta:
        model = Supplier
        fields = [
            'supplier_type', 'name', 'name_ar', 'trading_name', 'email', 'phone',
            'mobile', 'website', 'contact_person', 'contact_position',
            'contact_email', 'contact_phone', 'address', 'city', 'country',
            'postal_code', 'tax_number', 'registration_number', 'bank_name',
            'bank_account_name', 'bank_account_number', 'bank_iban', 'bank_swift',
            'currency', 'payment_terms', 'credit_limit', 'rating', 'notes', 'is_active'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class SupplierContactForm(BootstrapFormMixin, forms.ModelForm):
    """Form for SupplierContact model."""

    class Meta:
        model = SupplierContact
        fields = ['name', 'position', 'department', 'email', 'phone', 'mobile', 'is_primary', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


SupplierContactFormSet = forms.inlineformset_factory(
    Supplier, SupplierContact,
    form=SupplierContactForm,
    extra=1,
    can_delete=True
)


class PurchaseOrderForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for PurchaseOrder model."""

    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier', 'po_date', 'expected_date', 'reference',
            'currency', 'status', 'notes', 'terms'
        ]
        widgets = {
            'po_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'terms': forms.Textarea(attrs={'rows': 3}),
        }


class PurchaseOrderLineForm(BootstrapFormMixin, forms.ModelForm):
    """Form for PurchaseOrderLine model."""

    class Meta:
        model = PurchaseOrderLine
        fields = ['product', 'description', 'quantity', 'unit_price', 'tax_rate']


PurchaseOrderLineFormSet = forms.inlineformset_factory(
    PurchaseOrder, PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    extra=1,
    can_delete=True
)
