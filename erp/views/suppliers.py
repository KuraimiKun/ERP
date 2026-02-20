"""
ERP Views – Suppliers, Purchase Orders, Supplier Invoices & Payments
"""

from django.db.models import Q
from django.utils import timezone

from erp.models import (
    Supplier, PurchaseOrder,
    SupplierInvoice, SupplierInvoiceLine, SupplierPayment, SupplierPaymentAllocation,
    Product, TaxRate,
)
from erp.forms import (
    SupplierForm, SupplierContactFormSet,
    PurchaseOrderForm, PurchaseOrderLineFormSet,
    SupplierInvoiceForm, SupplierInvoiceLineFormSet,
    SupplierPaymentForm,
)
from erp.services import (
    get_supplier_id, get_po_number,
    get_supplier_invoice_number, get_supplier_payment_number,
    create_supplier_invoice_journal_entry,
    create_supplier_payment_journal_entry,
    create_purchase_order_journal_entry,
)
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
        'payments': supplier.payments.order_by('-payment_date')[:10],
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
        'lines': order.lines.select_related('product', 'tax_rate').all(),
        'supplier_invoices': order.supplier_invoices.all(),
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

            # If PO is created with approved status, adjust inventory
            if order.status == PurchaseOrder.Status.APPROVED:
                from erp.services.inventory import adjust_inventory_for_purchase_order
                try:
                    adjust_inventory_for_purchase_order(order)
                except Exception as e:
                    messages.warning(request, f'تم إنشاء الطلب لكن فشل تحديث المخزون: {e}')

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
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'tax_rates': TaxRate.objects.filter(company=company, is_active=True),
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
            old_status = PurchaseOrder.objects.get(pk=order.pk).status
            form.save()
            formset.save()

            order.calculate_totals()
            order.save()

            # If status changed to approved, adjust inventory
            if old_status != PurchaseOrder.Status.APPROVED and order.status == PurchaseOrder.Status.APPROVED:
                from erp.services.inventory import adjust_inventory_for_purchase_order
                try:
                    adjust_inventory_for_purchase_order(order)
                except Exception as e:
                    messages.warning(request, f'تم تحديث الطلب لكن فشل تحديث المخزون: {e}')

            messages.success(request, f'Purchase Order {order.po_number} updated successfully.')
            return redirect('erp:purchase_order_detail', pk=order.pk)
    else:
        form = PurchaseOrderForm(instance=order, company=company)
        formset = PurchaseOrderLineFormSet(instance=order)

    return render(request, 'erp/purchase_orders/form.html', {
        'form': form,
        'formset': formset,
        'products': Product.objects.filter(company=company, is_active=True).order_by('name'),
        'tax_rates': TaxRate.objects.filter(company=company, is_active=True),
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


# ── Purchase Order Approval ─────────────────────────────────────────────────

@staff_member_required
def purchase_order_approve(request, pk):
    company = get_user_company(request.user)
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)

    if request.method == 'POST':
        if order.status not in ('draft', 'pending'):
            messages.error(request, 'لا يمكن اعتماد هذا الطلب بحالته الحالية.')
            return redirect('erp:purchase_order_detail', pk=order.pk)

        # Get approving employee if available
        from erp.models import Employee
        try:
            employee = Employee.objects.get(user=request.user, company=company)
            order.approved_by = employee
        except Employee.DoesNotExist:
            pass

        order.approval_date = timezone.now()
        order.status = PurchaseOrder.Status.APPROVED
        order.save()

        # Adjust inventory — increment stock for received products
        from erp.services.inventory import adjust_inventory_for_purchase_order
        try:
            adjust_inventory_for_purchase_order(order)
        except Exception as e:
            messages.warning(request, f'تم اعتماد الطلب لكن فشل تحديث المخزون: {e}')

        # Create accrual journal entry
        try:
            create_purchase_order_journal_entry(order, request.user)
        except Exception:
            pass  # Don't fail if journal entry creation fails

        messages.success(request, f'تم اعتماد أمر الشراء {order.po_number}.')
        return redirect('erp:purchase_order_detail', pk=order.pk)

    return render(request, 'erp/purchase_orders/detail.html', {
        'order': order,
        'lines': order.lines.all(),
    })


# ── Purchase Order → Supplier Invoice Conversion ────────────────────────────

@staff_member_required
def purchase_order_create_invoice(request, pk):
    """Create a supplier invoice from a purchase order."""
    company = get_user_company(request.user)
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)

    if request.method == 'POST':
        # Create supplier invoice pre-filled from PO
        sinv_number = get_supplier_invoice_number(company)
        sinv = SupplierInvoice.objects.create(
            company=company,
            supplier=order.supplier,
            invoice_number=sinv_number,
            supplier_invoice_number=request.POST.get('supplier_invoice_number', ''),
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date(),
            purchase_order=order,
            currency=order.currency,
            status=SupplierInvoice.Status.DRAFT,
        )

        # Copy PO lines to invoice lines
        for po_line in order.lines.all():
            SupplierInvoiceLine.objects.create(
                invoice=sinv,
                description=po_line.description,
                quantity=po_line.quantity,
                unit_price=po_line.unit_price,
                tax_rate=po_line.tax_rate,
            )

        # Calculate totals & save
        sinv.calculate_totals()
        sinv.save()

        messages.success(request, f'تم إنشاء فاتورة المورد {sinv.invoice_number} من أمر الشراء {order.po_number}.')
        return redirect('erp:supplier_invoice_edit', pk=sinv.pk)

    return render(request, 'erp/purchase_orders/detail.html', {
        'order': order,
        'lines': order.lines.all(),
    })


# ── Supplier Invoices ───────────────────────────────────────────────────────

@staff_member_required
def supplier_invoice_list(request):
    company = get_user_company(request.user)
    invoices = SupplierInvoice.objects.filter(company=company).select_related('supplier', 'currency')

    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)

    search = request.GET.get('search')
    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(supplier__name__icontains=search) |
            Q(supplier_invoice_number__icontains=search)
        )

    return render(request, 'erp/supplier_invoices/list.html', {
        'invoices': invoices.order_by('-invoice_date')[:100],
        'statuses': SupplierInvoice.Status.choices,
    })


@staff_member_required
def supplier_invoice_detail(request, pk):
    company = get_user_company(request.user)
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)

    return render(request, 'erp/supplier_invoices/detail.html', {
        'invoice': invoice,
        'lines': invoice.lines.select_related('tax_rate', 'account').all(),
        'payments': invoice.payment_allocations.select_related('payment').all(),
    })


@staff_member_required
def supplier_invoice_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = SupplierInvoiceForm(request.POST, company=company)
        formset = SupplierInvoiceLineFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.company = company
            invoice.invoice_number = get_supplier_invoice_number(company)
            invoice.save()

            formset.instance = invoice
            formset.save()

            invoice.calculate_totals()
            invoice.save()

            # Auto-generate journal entry
            try:
                create_supplier_invoice_journal_entry(invoice, request.user)
            except Exception:
                pass

            messages.success(request, f'تم إنشاء فاتورة المورد {invoice.invoice_number}.')
            return redirect('erp:supplier_invoice_detail', pk=invoice.pk)
    else:
        form = SupplierInvoiceForm(company=company)
        formset = SupplierInvoiceLineFormSet()

        # Pre-fill from query params
        supplier_id = request.GET.get('supplier')
        if supplier_id:
            form.fields['supplier'].initial = supplier_id
        po_id = request.GET.get('po')
        if po_id:
            form.fields['purchase_order'].initial = po_id

    return render(request, 'erp/supplier_invoices/form.html', {
        'form': form,
        'formset': formset,
        'title': 'إنشاء فاتورة مورد',
        'submit_text': 'حفظ الفاتورة',
    })


@staff_member_required
def supplier_invoice_edit(request, pk):
    company = get_user_company(request.user)
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)

    if request.method == 'POST':
        form = SupplierInvoiceForm(request.POST, instance=invoice, company=company)
        formset = SupplierInvoiceLineFormSet(request.POST, instance=invoice)

        if form.is_valid() and formset.is_valid():
            invoice = form.save()
            formset.save()

            invoice.calculate_totals()
            invoice.save()

            messages.success(request, f'تم تحديث فاتورة المورد {invoice.invoice_number}.')
            return redirect('erp:supplier_invoice_detail', pk=invoice.pk)
    else:
        form = SupplierInvoiceForm(instance=invoice, company=company)
        formset = SupplierInvoiceLineFormSet(instance=invoice)

    return render(request, 'erp/supplier_invoices/form.html', {
        'form': form,
        'formset': formset,
        'invoice': invoice,
        'title': f'تعديل فاتورة المورد: {invoice.invoice_number}',
        'submit_text': 'حفظ التغييرات',
    })


@staff_member_required
def supplier_invoice_delete(request, pk):
    company = get_user_company(request.user)
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)

    if request.method == 'POST':
        number = invoice.invoice_number
        invoice.delete()
        messages.success(request, f'تم حذف فاتورة المورد {number}.')
        return redirect('erp:supplier_invoice_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': invoice,
        'object_type': 'فاتورة مورد',
        'cancel_url': reverse('erp:supplier_invoice_detail', args=[pk]),
    })


# ── Supplier Payments ───────────────────────────────────────────────────────

@staff_member_required
def supplier_payment_list(request):
    company = get_user_company(request.user)
    payments = SupplierPayment.objects.filter(company=company).select_related('supplier', 'currency', 'payment_method')

    search = request.GET.get('search')
    if search:
        payments = payments.filter(
            Q(payment_number__icontains=search) |
            Q(supplier__name__icontains=search)
        )

    supplier_filter = request.GET.get('supplier')
    if supplier_filter:
        payments = payments.filter(supplier_id=supplier_filter)

    from django.db.models import Sum, Count
    stats = payments.aggregate(
        total_count=Count('id'),
        total_amount=Sum('amount'),
        total_unallocated=Sum('unallocated_amount'),
    )

    suppliers = Supplier.objects.filter(company=company, is_active=True).order_by('name')

    return render(request, 'erp/supplier_payments/list.html', {
        'payments': payments.order_by('-payment_date')[:100],
        'stats': stats,
        'suppliers': suppliers,
        'selected_supplier': supplier_filter or '',
    })


@staff_member_required
def supplier_payment_detail(request, pk):
    company = get_user_company(request.user)
    payment = get_object_or_404(SupplierPayment, pk=pk, company=company)

    return render(request, 'erp/supplier_payments/detail.html', {
        'payment': payment,
        'allocations': payment.allocations.select_related('invoice', 'invoice__supplier').all(),
    })


@staff_member_required
def supplier_payment_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST, company=company)

        if form.is_valid():
            payment = form.save(commit=False)
            payment.company = company
            payment.payment_number = get_supplier_payment_number(company)
            payment.save()

            # Handle invoice allocation
            invoice = form.cleaned_data.get('supplier_invoice')
            if invoice:
                alloc_amount = min(payment.amount, invoice.balance_due)
                SupplierPaymentAllocation.objects.create(
                    payment=payment,
                    invoice=invoice,
                    amount=alloc_amount,
                )
                payment.allocated_amount = alloc_amount
                payment.save()

                # Update invoice paid/balance
                invoice.paid_amount += alloc_amount
                invoice.calculate_totals()
                invoice.save()

            # Auto-generate journal entry
            try:
                create_supplier_payment_journal_entry(payment, request.user)
            except Exception:
                pass

            messages.success(request, f'تم تسجيل دفعة المورد {payment.payment_number}.')
            return redirect('erp:supplier_payment_detail', pk=payment.pk)
    else:
        form = SupplierPaymentForm(company=company)

        # Pre-fill from query params
        supplier_id = request.GET.get('supplier')
        if supplier_id:
            form.fields['supplier'].initial = supplier_id
            form.initial['supplier'] = supplier_id
            # Re-init to filter invoices by supplier
            form = SupplierPaymentForm(company=company, initial={'supplier': supplier_id})

        invoice_id = request.GET.get('invoice')
        if invoice_id:
            form.fields['supplier_invoice'].initial = invoice_id

    return render(request, 'erp/supplier_payments/form.html', {
        'form': form,
        'title': 'تسجيل دفعة للمورد',
        'submit_text': 'حفظ الدفعة',
    })


@staff_member_required
def supplier_payment_delete(request, pk):
    company = get_user_company(request.user)
    payment = get_object_or_404(SupplierPayment, pk=pk, company=company)

    if request.method == 'POST':
        # Reverse allocations before deletion
        for alloc in payment.allocations.all():
            inv = alloc.invoice
            inv.paid_amount -= alloc.amount
            inv.calculate_totals()
            inv.save()

        number = payment.payment_number
        payment.delete()
        messages.success(request, f'تم حذف دفعة المورد {number}.')
        return redirect('erp:supplier_payment_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': payment,
        'object_type': 'دفعة مورد',
        'cancel_url': reverse('erp:supplier_payment_detail', args=[pk]),
    })
