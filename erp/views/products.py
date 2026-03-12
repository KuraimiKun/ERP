"""
ERP Views – Products & Product Categories
"""

from django.db.models import Q, F

from erp.models import Product, ProductCategory
from erp.forms import ProductCategoryForm, ProductForm, ProductSupplierFormSet
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required, paginate_qs, apply_sorting,
)


# ── Product Categories ──────────────────────────────────────────────────────

@staff_member_required
def product_category_list(request):
    company = get_user_company(request.user)
    categories = ProductCategory.objects.filter(company=company)

    categories, current_sort, current_order = apply_sorting(
        request, categories,
        allowed_fields=['name', 'created_at'],
        default='name',
    )
    page_obj, query_string = paginate_qs(request, categories)

    return render(request, 'erp/product_categories/list.html', {
        'categories': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def product_category_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = ProductCategoryForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, f'تمت إضافة تصنيف المنتج "{obj.name}" بنجاح.')
            return redirect('erp:product_category_list')
    else:
        form = ProductCategoryForm(company=company)
    return render(request, 'erp/product_categories/form.html', {
        'form': form, 'title': 'إضافة تصنيف منتج', 'submit_text': 'حفظ',
    })


@staff_member_required
def product_category_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(ProductCategory, pk=pk, company=company)
    if request.method == 'POST':
        form = ProductCategoryForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث تصنيف المنتج بنجاح.')
            return redirect('erp:product_category_list')
    else:
        form = ProductCategoryForm(instance=obj, company=company)
    return render(request, 'erp/product_categories/form.html', {
        'form': form, 'title': 'تعديل تصنيف منتج', 'submit_text': 'حفظ التغييرات',
    })


@staff_member_required
def product_category_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(ProductCategory, pk=pk, company=company)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'تم حذف تصنيف المنتج بنجاح.')
        return redirect('erp:product_category_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': obj, 'object_type': 'تصنيف منتج',
        'cancel_url': reverse('erp:product_category_list'),
    })


# ── Products ────────────────────────────────────────────────────────────────

@staff_member_required
def product_list(request):
    company = get_user_company(request.user)
    products = Product.objects.filter(company=company).select_related(
        'category', 'supplier', 'currency', 'tax_rate'
    )

    search = request.GET.get('search', '').strip()
    if search:
        products = products.filter(
            Q(name__icontains=search) | Q(sku__icontains=search) |
            Q(barcode__icontains=search) | Q(name_ar__icontains=search)
        )
    cat = request.GET.get('category')
    if cat:
        products = products.filter(category_id=cat)
    ptype = request.GET.get('type')
    if ptype:
        products = products.filter(product_type=ptype)
    low_stock = request.GET.get('low_stock')
    if low_stock:
        products = products.filter(
            track_inventory=True,
            quantity_on_hand__lte=F('reorder_level')
        )

    products, current_sort, current_order = apply_sorting(
        request, products,
        allowed_fields=['name', 'sku', 'selling_price', 'quantity_on_hand', 'product_type'],
        default='name',
    )
    page_obj, query_string = paginate_qs(request, products)

    return render(request, 'erp/products/list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'categories': ProductCategory.objects.filter(company=company, is_active=True),
        'product_types': Product.ProductType.choices,
        'current_sort': current_sort,
        'current_order': current_order,
    })


@staff_member_required
def product_detail(request, pk):
    company = get_user_company(request.user)
    product = get_object_or_404(Product, pk=pk, company=company)
    suppliers = product.product_suppliers.select_related('supplier', 'currency').all()
    invoice_lines = product.invoice_lines.select_related('invoice__customer').order_by('-invoice__invoice_date')[:20]
    po_lines = product.purchase_order_lines.select_related('purchase_order__supplier').order_by('-purchase_order__po_date')[:20]
    return render(request, 'erp/products/detail.html', {
        'product': product,
        'suppliers': suppliers,
        'invoice_lines': invoice_lines,
        'po_lines': po_lines,
    })


@staff_member_required
def product_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, company=company)
        supplier_formset = ProductSupplierFormSet(request.POST)
        if form.is_valid() and supplier_formset.is_valid():
            product = form.save(commit=False)
            product.company = company
            product.save()
            supplier_formset.instance = product
            supplier_formset.save()
            messages.success(request, f'تمت إضافة المنتج "{product.name}" بنجاح.')
            return redirect('erp:product_detail', pk=product.pk)
    else:
        form = ProductForm(company=company)
        supplier_formset = ProductSupplierFormSet()
    return render(request, 'erp/products/form.html', {
        'form': form, 'supplier_formset': supplier_formset,
        'title': 'إضافة منتج', 'submit_text': 'حفظ المنتج',
    })


@staff_member_required
def product_edit(request, pk):
    company = get_user_company(request.user)
    product = get_object_or_404(Product, pk=pk, company=company)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, company=company)
        supplier_formset = ProductSupplierFormSet(request.POST, instance=product)
        if form.is_valid() and supplier_formset.is_valid():
            form.save()
            supplier_formset.save()
            messages.success(request, 'تم تحديث المنتج بنجاح.')
            return redirect('erp:product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product, company=company)
        supplier_formset = ProductSupplierFormSet(instance=product)
    return render(request, 'erp/products/form.html', {
        'form': form, 'supplier_formset': supplier_formset,
        'title': 'تعديل منتج', 'submit_text': 'حفظ التغييرات', 'product': product,
    })


@staff_member_required
def product_delete(request, pk):
    company = get_user_company(request.user)
    product = get_object_or_404(Product, pk=pk, company=company)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'تم حذف المنتج بنجاح.')
        return redirect('erp:product_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': product, 'object_type': 'منتج',
        'cancel_url': reverse('erp:product_detail', args=[pk]),
    })
