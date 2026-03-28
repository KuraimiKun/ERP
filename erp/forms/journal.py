"""
ERP Forms - Journal Entries

Forms for JournalEntry, JournalEntryLine and their formsets.
"""
from django.utils.translation import gettext_lazy as _


from decimal import Decimal

from django import forms

from erp.models import JournalEntry, JournalEntryLine, Account
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class JournalEntryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """نموذج قيد اليومية"""

    class Meta:
        model = JournalEntry
        fields = ['entry_number', 'entry_date', 'entry_type', 'description', 'reference', 'fiscal_year']
        widgets = {
            'entry_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'entry_number': 'رقم القيد',
            'entry_date': 'التاريخ',
            'entry_type': 'نوع القيد',
            'description': 'البيان',
            'reference': 'المرجع',
            'fiscal_year': 'السنة المالية',
        }


class JournalEntryLineForm(BootstrapFormMixin, forms.ModelForm):
    """نموذج سطر قيد اليومية"""

    class Meta:
        model = JournalEntryLine
        fields = ['account', 'description', 'debit_amount', 'credit_amount']
        labels = {
            'account': 'الحساب',
            'description': 'البيان',
            'debit_amount': 'مدين',
            'credit_amount': 'دائن',
        }

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company:
            self.fields['account'].queryset = Account.objects.filter(company=company, is_active=True).order_by('code')


class BaseJournalEntryLineFormSet(forms.BaseInlineFormSet):
    """FormSet أساسي لأسطر قيود اليومية مع دعم فلترة الشركة"""

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['company'] = self.company
        return super()._construct_form(i, **kwargs)

    def clean(self):
        """Validate that total debits equal total credits."""
        super().clean()
        # Only run if individual forms are all valid.
        if any(form.errors for form in self.forms):
            return
        total_debit = Decimal('0')
        total_credit = Decimal('0')
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            total_debit += form.cleaned_data.get('debit_amount') or Decimal('0')
            total_credit += form.cleaned_data.get('credit_amount') or Decimal('0')
        if total_debit != total_credit:
            raise forms.ValidationError(
                _(
                    'إجمالي المدين (%(debit)s) يجب أن يساوي إجمالي الدائن (%(credit)s). '
                    'الفرق: %(diff)s'
                ) % {
                    'debit': total_debit,
                    'credit': total_credit,
                    'diff': abs(total_debit - total_credit),
                }
            )


JournalEntryLineFormSet = forms.inlineformset_factory(
    JournalEntry,
    JournalEntryLine,
    form=JournalEntryLineForm,
    formset=BaseJournalEntryLineFormSet,
    extra=4,
    can_delete=True,
    min_num=2,
    validate_min=True,
)
