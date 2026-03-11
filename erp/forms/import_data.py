"""
ERP Forms – Data Import

File upload form for the bulk import wizard.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from .mixins import BootstrapFormMixin

ENTITY_CHOICES = [
    ('', _('-- Select --')),
    ('customers', _('Customers')),
    ('products', _('Products')),
    ('suppliers', _('Suppliers')),
    ('employees', _('Employees')),
]

ALLOWED_EXTENSIONS = ('.csv', '.xlsx')


class ImportUploadForm(BootstrapFormMixin, forms.Form):
    """Step 1 – choose entity and upload CSV/Excel file."""
    entity = forms.ChoiceField(
        choices=ENTITY_CHOICES,
        label=_('Data Type'),
    )
    file = forms.FileField(
        label=_('File'),
        help_text=_('Upload a CSV or Excel (.xlsx) file.'),
    )

    def clean_file(self):
        f = self.cleaned_data['file']
        name = f.name.lower()
        if not name.endswith(ALLOWED_EXTENSIONS):
            raise forms.ValidationError(
                _('Unsupported file format. Please upload a CSV or Excel (.xlsx) file.')
            )
        # 10 MB limit
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError(
                _('File is too large. Maximum size is 10 MB.')
            )
        return f
