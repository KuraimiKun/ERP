"""
ERP Forms - Products

Forms for ProductCategory, Product, ProductSupplier.
"""
from django import forms

from erp.models import Product, ProductCategory, ProductSupplier
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class ProductCategoryForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for ProductCategory model."""

    class Meta:
        model = ProductCategory
        fields = ['name', 'name_ar', 'code', 'description', 'parent', 'is_active', 'sort_order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class ProductForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Product model."""

    class Meta:
        model = Product
        fields = [
            'sku', 'barcode', 'name', 'name_ar', 'description', 'image',
            'product_type', 'category', 'currency',
            'selling_price', 'cost_price', 'min_selling_price', 'tax_rate',
            'track_inventory', 'quantity_on_hand', 'reorder_level',
            'reorder_quantity', 'unit_of_measure',
            'supplier', 'supplier_sku',
            'is_active', 'notes',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Auto-select the base currency if none chosen yet
        if not self.instance.pk and not self.initial.get('currency'):
            from erp.models import Currency
            base = Currency.objects.filter(is_base=True).first()
            if base:
                self.initial['currency'] = base.pk


class ProductSupplierForm(BootstrapFormMixin, forms.ModelForm):
    """Form for ProductSupplier (additional suppliers per product)."""

    class Meta:
        model = ProductSupplier
        fields = [
            'supplier', 'supplier_sku', 'supplier_price', 'currency',
            'lead_time_days', 'min_order_qty', 'is_preferred', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


ProductSupplierFormSet = forms.inlineformset_factory(
    Product, ProductSupplier,
    form=ProductSupplierForm,
    extra=1,
    can_delete=True,
)
