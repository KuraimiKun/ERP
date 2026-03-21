"""
ERP Forms - Journal Entries

Forms for JournalEntry, JournalEntryLine and their formsets.
"""
from django.utils.translation import gettext_lazy as _


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
