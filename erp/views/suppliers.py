"""
ERP Views – Suppliers & Purchase Orders
"""

from django.db.models import Q

from erp.models import Supplier, PurchaseOrder
from erp.forms import (
    SupplierForm, SupplierContactFormSet,
    PurchaseOrderForm, PurchaseOrderLineFormSet,
)
from erp.services import get_supplier_id, get_po_number
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required,
)


# ── Suppliers ───────────────────────────────────────────────────────────────

@staff_member_required
def supplier_list(request):
    company = get_user_company(request.user)
    suppliers = Supplier.objects.filter(company=company).order_by('name')

    supplier_type = request.GET.get('type')
    if supplier_type:
        suppliers = suppliers.filter(supplier_type=supplier_type)

    search = request.GET.get('search')
    if search:
        suppliers = suppliers.filter(
            Q(name__icontains=search) |
            Q(email__icontains=search) |
            Q(supplier_id__icontains=search)
        )

    return render(request, 'erp/suppliers/list.html', {
        'suppliers': suppliers,
        'supplier_types': Supplier.SupplierType.choices,
    })


@staff_member_required
def supplier_detail(request, pk):
    company = get_user_company(request.user)
    supplier = get_object_or_404(Supplier, pk=pk, company=company)

    return render(request, 'erp/suppliers/detail.html', {
        'supplier': supplier,
        'purchase_orders': supplier.purchase_orders.order_by('-po_date')[:10],
        'invoices': supplier.invoices.order_by('-invoice_date')[:10],
        'contacts': supplier.contacts.all(),
        'documents': supplier.documents.order_by('-created_at'),
    })


@staff_member_required
def supplier_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = SupplierForm(request.POST, company=company)
        formset = SupplierContactFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            supplier = form.save(commit=False)
            supplier.company = company
            supplier.supplier_id = get_supplier_id(company)
            supplier.save()

            formset.instance = supplier
            formset.save()

            messages.success(request, f'Supplier "{supplier.name}" created successfully.')
            return redirect('erp:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(company=company)
        formset = SupplierContactFormSet()

    return render(request, 'erp/suppliers/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Add Supplier',
        'submit_text': 'Create Supplier',
    })


@staff_member_required
def supplier_edit(request, pk):
    company = get_user_company(request.user)
    supplier = get_object_or_404(Supplier, pk=pk, company=company)

    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier, company=company)
        formset = SupplierContactFormSet(request.POST, instance=supplier)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Supplier "{supplier.name}" updated successfully.')
            return redirect('erp:supplier_detail', pk=supplier.pk)
    else:
        form = SupplierForm(instance=supplier, company=company)
        formset = SupplierContactFormSet(instance=supplier)

    return render(request, 'erp/suppliers/form.html', {
        'form': form,
        'formset': formset,
        'supplier': supplier,
        'title': f'Edit Supplier: {supplier.name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def supplier_delete(request, pk):
    company = get_user_company(request.user)
    supplier = get_object_or_404(Supplier, pk=pk, company=company)

    if request.method == 'POST':
        name = supplier.name
        supplier.delete()
        messages.success(request, f'Supplier "{name}" deleted successfully.')
        return redirect('erp:supplier_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': supplier,
        'object_type': 'Supplier',
        'cancel_url': reverse('erp:supplier_detail', args=[pk]),
    })


# ── Purchase Orders ─────────────────────────────────────────────────────────

@staff_member_required
def purchase_order_list(request):
    company = get_user_company(request.user)
    orders = PurchaseOrder.objects.filter(company=company).select_related('supplier', 'currency')

    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)

    return render(request, 'erp/purchase_orders/list.html', {
        'orders': orders.order_by('-po_date')[:100],
        'statuses': PurchaseOrder.Status.choices,
    })


@staff_member_required
def purchase_order_detail(request, pk):
    company = get_user_company(request.user)
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)

    return render(request, 'erp/purchase_orders/detail.html', {
        'order': order,
        'lines': order.lines.all(),
    })


@staff_member_required
def purchase_order_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, company=company)
        formset = PurchaseOrderLineFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            order.company = company
            order.po_number = get_po_number(company)
            order.save()

            formset.instance = order
            formset.save()

            order.calculate_totals()
            order.save()

            messages.success(request, f'Purchase Order {order.po_number} created successfully.')
            return redirect('erp:purchase_order_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm(company=company)
        formset = PurchaseOrderLineFormSet()

        supplier_id = request.GET.get('supplier')
        if supplier_id:
            form.fields['supplier'].initial = supplier_id

    return render(request, 'erp/purchase_orders/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Create Purchase Order',
        'submit_text': 'Create Order',
    })


@staff_member_required
def purchase_order_edit(request, pk):
    company = get_user_company(request.user)
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=order, company=company)
        formset = PurchaseOrderLineFormSet(request.POST, instance=order)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            order.calculate_totals()
            order.save()

            messages.success(request, f'Purchase Order {order.po_number} updated successfully.')
            return redirect('erp:purchase_order_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm(instance=order, company=company)
        formset = PurchaseOrderLineFormSet(instance=order)

    return render(request, 'erp/purchase_orders/form.html', {
        'form': form,
        'formset': formset,
        'order': order,
        'title': f'Edit Purchase Order: {order.po_number}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def purchase_order_delete(request, pk):
    company = get_user_company(request.user)
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)

    if request.method == 'POST':
        number = order.po_number
        order.delete()
        messages.success(request, f'Purchase Order {number} deleted successfully.')
        return redirect('erp:purchase_order_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': order,
        'object_type': 'Purchase Order',
        'cancel_url': reverse('erp:purchase_order_detail', args=[pk]),
    })
