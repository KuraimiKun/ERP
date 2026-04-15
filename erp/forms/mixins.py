"""
ERP Forms - Base Mixins

Shared form mixins used across all ERP form modules.
"""
from django import forms


class CompanyFilterMixin:
    """Mixin to filter querysets by company."""

    def __init__(self, *args, company=None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)
        self.filter_querysets_by_company()

    def filter_querysets_by_company(self):
        """Filter all ForeignKey fields by company."""
        if not self.company:
            return

        for field_name, field in self.fields.items():
            if hasattr(field, 'queryset'):
                model = field.queryset.model
                if hasattr(model, 'company'):
                    field.queryset = field.queryset.filter(company=self.company)


class BootstrapFormMixin:
    """Mixin to add Bootstrap 5 classes to form fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap_classes()

    def add_bootstrap_classes(self):
        """Add Bootstrap form-control class to all fields."""
        for field_name, field in self.fields.items():
            widget = field.widget
            existing_class = widget.attrs.get('class', '')

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = f'{existing_class} form-check-input'.strip()
            elif isinstance(widget, forms.Select):
                widget.attrs['class'] = f'{existing_class} form-select'.strip()
            elif isinstance(widget, forms.Textarea):
                widget.attrs['class'] = f'{existing_class} form-control'.strip()
                widget.attrs.setdefault('rows', 3)
            elif isinstance(widget, forms.FileInput):
                widget.attrs['class'] = f'{existing_class} form-control'.strip()
            else:
                widget.attrs['class'] = f'{existing_class} form-control'.strip()
