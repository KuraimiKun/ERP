"""
ERP Forms - Finance

Forms for Customer, Invoice, InvoiceLine, Payment, Expense, Account,
TaxRate, PaymentMethod, ExpenseCategory.
"""
from django.utils.translation import gettext_lazy as _


from decimal import Decimal

from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator

from erp.models import (
    Customer, Invoice, InvoiceLine, Payment,
    Expense, ExpenseCategory, Account, TaxRate, PaymentMethod,
)
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class CustomerForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Customer model."""

    class Meta:
        model = Customer
        fields = [
            'customer_type', 'name', 'name_ar', 'email', 'phone', 'mobile',
            'website', 'tax_id', 'tax_number', 'assigned_to', 'is_active',
            'billing_address', 'billing_city', 'billing_state',
            'billing_country', 'billing_postal_code',
            'shipping_address', 'shipping_city', 'shipping_state',
            'shipping_country', 'shipping_postal_code',
            'credit_limit', 'currency', 'payment_terms', 'notes',
        ]
        widgets = {
            'billing_address': forms.Textarea(attrs={'rows': 2}),
            'shipping_address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class InvoiceForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Invoice model."""

    class Meta:
        model = Invoice
        # 'status' is intentionally excluded — transitions happen via dedicated
        # action endpoints (cancel, send, etc.), not free-form editing.
        fields = [
            'customer', 'invoice_type', 'invoice_date', 'due_date',
            'reference', 'currency', 'notes', 'terms'
        ]
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'terms': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        invoice_date = cleaned_data.get('invoice_date')
        due_date = cleaned_data.get('due_date')
        if invoice_date and due_date and due_date < invoice_date:
            self.add_error('due_date', _('تاريخ الاستحقاق لا يمكن أن يكون قبل تاريخ الفاتورة'))
        return cleaned_data


class InvoiceLineForm(BootstrapFormMixin, forms.ModelForm):
    """Form for InvoiceLine model."""

    quantity = forms.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        error_messages={'min_value': _('الكمية يجب أن تكون أكبر من صفر')},
    )
    unit_price = forms.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        error_messages={'min_value': _('سعر الوحدة لا يمكن أن يكون سالباً')},
    )
    discount_percent = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False, initial=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        error_messages={
            'min_value': _('نسبة الخصم لا يمكن أن تكون سالبة'),
            'max_value': _('نسبة الخصم لا يمكن أن تتجاوز 100%'),
        },
    )

    class Meta:
        model = InvoiceLine
        fields = ['product', 'service_pricing', 'description', 'quantity', 'unit_price', 'discount_percent', 'tax_rate']


InvoiceLineFormSet = forms.inlineformset_factory(
    Invoice, InvoiceLine,
    form=InvoiceLineForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PaymentForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Payment model."""

    invoice = forms.ModelChoiceField(
        queryset=Invoice.objects.none(),
        required=False,
        label=_('الفاتورة'),
        help_text=_('اختر فاتورة لربط الدفعة بها (اختياري)'),
    )

    class Meta:
        model = Payment
        fields = [
            'customer', 'invoice', 'payment_type', 'payment_date', 'payment_method',
            'amount', 'currency', 'reference_number', 'notes'
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show invoices with outstanding balance for this company
        if self.company:
            self.fields['invoice'].queryset = Invoice.objects.filter(
                company=self.company,
                status__in=['sent', 'partial', 'overdue', 'draft'],
            ).select_related('customer').order_by('-invoice_date')

        # If customer is pre-selected (e.g. from invoice detail page),
        # filter invoices to that customer
        customer_id = self.data.get('customer') or (self.initial.get('customer') if self.initial else None)
        if customer_id:
            self.fields['invoice'].queryset = self.fields['invoice'].queryset.filter(
                customer_id=customer_id
            )

    def clean(self):
        cleaned_data = super().clean()
        invoice = cleaned_data.get('invoice')
        amount = cleaned_data.get('amount')
        payment_currency = cleaned_data.get('currency')

        if invoice and amount is not None:
            if amount <= 0:
                self.add_error('amount', _('يجب أن يكون المبلغ أكبر من الصفر'))
            else:
                # Convert to invoice currency before checking overpayment
                if payment_currency and payment_currency.pk != invoice.currency_id:
                    from decimal import Decimal, ROUND_HALF_UP
                    pay_rate = payment_currency.exchange_rate or Decimal('1')
                    inv_rate = invoice.exchange_rate_at_date or Decimal('1')
                    amount_in_invoice_ccy = (amount * pay_rate / inv_rate).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                else:
                    amount_in_invoice_ccy = amount

                if amount_in_invoice_ccy > invoice.balance_due:
                    self.add_error(
                        'amount',
                        _(
                            f'المبلغ المدخل يعادل ({amount_in_invoice_ccy} {invoice.currency.code}) '
                            f'وهو أكبر من الرصيد المستحق ({invoice.balance_due} {invoice.currency.code}). '
                            'يُرجى إدخال مبلغ لا يتجاوز الرصيد المستحق.'
                        ),
                    )

        return cleaned_data


class ExpenseForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Expense model."""

    class Meta:
        model = Expense
        fields = [
            'category', 'supplier', 'employee', 'description', 'expense_date',
            'amount', 'tax_amount', 'currency', 'payment_method',
            'payment_reference', 'status', 'notes'
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class AccountForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Account (Chart of Accounts) model."""

    class Meta:
        model = Account
        fields = [
            'code', 'name', 'name_ar', 'account_type', 'parent',
            'opening_balance', 'description', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class TaxRateForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for TaxRate model."""

    class Meta:
        model = TaxRate
        fields = ['name', 'name_ar', 'rate', 'is_default', 'is_active']


class PaymentMethodForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for PaymentMethod model."""

    class Meta:
        model = PaymentMethod
        fields = ['name', 'name_ar', 'code', 'is_active', 'requires_reference', 'account']


class ExpenseCategoryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for ExpenseCategory model."""

    class Meta:
        model = ExpenseCategory
        fields = ['name', 'name_ar', 'code', 'parent', 'account', 'is_active']
