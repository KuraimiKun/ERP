"""
ERP Forms - Services

Forms for ServiceCategory, ServicePricing, Quote, QuoteLine.
"""

from django import forms

from erp.models import ServiceCategory, ServicePricing, Quote, QuoteLine
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class ServiceCategoryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for ServiceCategory model."""

    class Meta:
        model = ServiceCategory
        fields = ["name", "name_ar", "code", "description", "parent", "is_active", "sort_order"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class ServicePricingForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for ServicePricing model."""

    class Meta:
        model = ServicePricing
        fields = [
            "name",
            "name_ar",
            "code",
            "website_service_name",
            "category",
            "description",
            "pricing_type",
            "currency",
            "base_price",
            "cost_price",
            "tax_rate",
            "is_tax_inclusive",
            "agent_commission_percent",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class QuoteForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Quote model."""

    class Meta:
        model = Quote
        fields = [
            "customer",
            "lead",
            "quote_date",
            "valid_until",
            "reference",
            "currency",
            "discount_percent",
            "status",
            "notes",
            "terms",
            "prepared_by",
        ]
        widgets = {
            "quote_date": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "terms": forms.Textarea(attrs={"rows": 4}),
        }


class QuoteLineForm(BootstrapFormMixin, forms.ModelForm):
    """Form for QuoteLine model."""

    class Meta:
        model = QuoteLine
        fields = ["product", "service_pricing", "description", "quantity", "unit_price", "discount_percent", "tax_rate"]


QuoteLineFormSet = forms.inlineformset_factory(Quote, QuoteLine, form=QuoteLineForm, extra=1, can_delete=True)
