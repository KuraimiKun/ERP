"""
ERP Forms - Supplier

Forms for Supplier, SupplierContact, PurchaseOrder, PurchaseOrderLine,
SupplierInvoice, SupplierInvoiceLine, SupplierPayment.
"""
from django.utils.translation import gettext_lazy as _


from django import forms

from erp.models import (
    Supplier, SupplierContact, PurchaseOrder, PurchaseOrderLine,
    SupplierInvoice, SupplierInvoiceLine, SupplierPayment,
)
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class SupplierForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Supplier model."""

    website = forms.CharField(max_length=200, required=False, help_text=_('مثال: www.example.com'))

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
            'supplier_type': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set a sensible default for supplier_type so it's not left blank
        if not self.initial.get('supplier_type') and not self.data.get('supplier_type'):
            self.initial['supplier_type'] = 'other'

    def clean_website(self):
        """Auto-prepend https:// if user enters a bare domain."""
        url = self.cleaned_data.get('website', '').strip()
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url


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
            'currency', 'notes', 'terms'
        ]
        widgets = {
            'po_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'terms': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Auto-set today's date and base currency for new POs
        if not self.instance.pk:
            from django.utils import timezone
            from erp.models import Currency
            if not self.initial.get('po_date'):
                self.initial['po_date'] = timezone.now().date().isoformat()
            if not self.initial.get('currency'):
                base = Currency.objects.filter(is_base=True).first()
                if base:
                    self.initial['currency'] = base.pk
            if not self.initial.get('status'):
                self.initial['status'] = 'draft'


class PurchaseOrderLineForm(BootstrapFormMixin, forms.ModelForm):
    """Form for PurchaseOrderLine model."""

    class Meta:
        model = PurchaseOrderLine
        fields = ['product', 'description', 'quantity', 'unit_price', 'tax_rate']


PurchaseOrderLineFormSet = forms.inlineformset_factory(
    PurchaseOrder, PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# ── Supplier Invoices ───────────────────────────────────────────────────────

class SupplierInvoiceForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for SupplierInvoice model."""

    class Meta:
        model = SupplierInvoice
        fields = [
            'supplier', 'invoice_date', 'due_date',
            'supplier_invoice_number', 'purchase_order',
            'currency', 'status', 'notes',
        ]
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.company:
            # Filter POs by company and only open statuses
            self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(
                company=self.company,
                status__in=['approved', 'sent', 'partial'],
            )
            self.fields['supplier'].queryset = Supplier.objects.filter(
                company=self.company, is_active=True,
            )


class SupplierInvoiceLineForm(BootstrapFormMixin, forms.ModelForm):
    """Form for SupplierInvoiceLine model."""

    class Meta:
        model = SupplierInvoiceLine
        fields = ['description', 'quantity', 'unit_price', 'tax_rate', 'account']


SupplierInvoiceLineFormSet = forms.inlineformset_factory(
    SupplierInvoice, SupplierInvoiceLine,
    form=SupplierInvoiceLineForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# ── Supplier Payments ───────────────────────────────────────────────────────

class SupplierPaymentForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for SupplierPayment model."""

    supplier_invoice = forms.ModelChoiceField(
        queryset=SupplierInvoice.objects.none(),
        required=False,
        label=_('فاتورة المورد'),
    )

    class Meta:
        model = SupplierPayment
        fields = [
            'supplier', 'supplier_invoice', 'payment_date',
            'payment_method', 'reference_number',
            'currency', 'amount', 'notes',
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.company:
            self.fields['supplier'].queryset = Supplier.objects.filter(
                company=self.company, is_active=True,
            )
            # Show supplier invoices with outstanding balance
            inv_qs = SupplierInvoice.objects.filter(
                company=self.company,
                status__in=['approved', 'partial', 'pending', 'draft'],
                balance_due__gt=0,
            ).select_related('supplier')

            # If supplier is already selected (via GET param or bound data),
            # filter invoices for that supplier
            supplier_id = None
            if self.data.get('supplier'):
                supplier_id = self.data.get('supplier')
            elif self.initial.get('supplier'):
                supplier_id = self.initial.get('supplier')

            if supplier_id:
                inv_qs = inv_qs.filter(supplier_id=supplier_id)

            self.fields['supplier_invoice'].queryset = inv_qs

    def clean(self):
        cleaned_data = super().clean()
        invoice = cleaned_data.get('supplier_invoice')
        amount = cleaned_data.get('amount')

        if invoice and amount:
            if amount > invoice.balance_due:
                # Allow overpayment but warn
                pass

        return cleaned_data
