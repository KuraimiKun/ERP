"""
ERP Views – Suppliers, Purchase Orders, Supplier Invoices & Payments
"""

import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.models import (
    Supplier, PurchaseOrder,
    SupplierInvoice, SupplierInvoiceLine, SupplierPayment, SupplierPaymentAllocation,
    Product, TaxRate, JournalEntry, Account,
)

_logger = logging.getLogger('erp.finance')
from erp.forms import (
    SupplierForm, SupplierContactFormSet,
    PurchaseOrderForm, PurchaseOrderLineFormSet,
    SupplierInvoiceForm, SupplierInvoiceLineFormSet,
    SupplierPaymentForm,
)
from django.utils.translation import gettext as _

from erp.services import (
    get_supplier_id, get_po_number,
    get_supplier_invoice_number, get_supplier_payment_number,
    create_supplier_invoice_journal_entry,
    create_supplier_payment_journal_entry,
    create_purchase_order_journal_entry,
)
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required, paginate_qs, apply_sorting,
)


# ── Suppliers ───────────────────────────────────────────────────────────────

@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def supplier_list(request):
    company = get_user_company(request.user)
    suppliers = Supplier.objects.filter(company=company)

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

    suppliers, current_sort, current_order = apply_sorting(
        request, suppliers,
        allowed_fields=['name', 'supplier_type', 'created_at'],
        default='name',
    )
    page_obj, query_string = paginate_qs(request, suppliers)

    return render(request, 'erp/suppliers/list.html', {
        'suppliers': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'supplier_types': Supplier.SupplierType.choices,
        'current_sort': current_sort,
        'current_order': current_order,
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
        'documents': supplier.documents.order_by('-created_at')[:50],
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
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def purchase_order_list(request):
    company = get_user_company(request.user)
    orders = PurchaseOrder.objects.filter(company=company).select_related('supplier', 'currency')

    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)

    orders, current_sort, current_order = apply_sorting(
        request, orders,
        allowed_fields=['po_number', 'po_date', 'total_amount', 'status'],
        default='-po_date',
    )
    page_obj, query_string = paginate_qs(request, orders)

    return render(request, 'erp/purchase_orders/list.html', {
        'orders': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statuses': PurchaseOrder.Status.choices,
        'current_sort': current_sort,
        'current_order': current_order,
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
            messages.error(request, _('Cannot approve this purchase order in its current state.'))
            return redirect('erp:purchase_order_detail', pk=order.pk)

        # Get approving employee if available
        from erp.models import Employee
        try:
            employee = Employee.objects.get(user=request.user, company=company)
            order.approved_by = employee
        except Employee.DoesNotExist:
            messages.warning(
                request,
                _('Employee record not found for your account — approval recorded without employee link.')
            )

        order.approval_date = timezone.now()
        order.status = PurchaseOrder.Status.APPROVED
        order.save()

        # NOTE: Stock is NOT incremented here. Physical receipt happens via
        # Goods Receipt Note (GRN). This accrual entry records the commitment.
        # Create accrual journal entry (DR GRNI / CR Accrued Liabilities)
        try:
            create_purchase_order_journal_entry(order, request.user)
        except Exception:
            pass  # Don't fail if journal entry creation fails

        messages.success(request, _('Purchase order %(number)s approved.') % {'number': order.po_number})
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

        messages.success(request, _('Supplier invoice %(sinv)s created from purchase order %(po)s.') % {'sinv': sinv.invoice_number, 'po': order.po_number})
        return redirect('erp:supplier_invoice_edit', pk=sinv.pk)

    return render(request, 'erp/purchase_orders/detail.html', {
        'order': order,
        'lines': order.lines.all(),
    })


# ── Supplier Invoices ───────────────────────────────────────────────────────

@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
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

    invoices, current_sort, current_order = apply_sorting(
        request, invoices,
        allowed_fields=['invoice_number', 'invoice_date', 'total_amount', 'status'],
        default='-invoice_date',
    )
    page_obj, query_string = paginate_qs(request, invoices)

    return render(request, 'erp/supplier_invoices/list.html', {
        'invoices': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statuses': SupplierInvoice.Status.choices,
        'current_sort': current_sort,
        'current_order': current_order,
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
                _logger.exception('Failed to create journal entry for supplier invoice %s', invoice.invoice_number)
                messages.warning(request, 'تحذير: تعذّر إنشاء القيد المحاسبي تلقائياً. يُرجى إنشاؤه يدوياً.')

            messages.success(request, _('Supplier invoice %(number)s created.') % {'number': invoice.invoice_number})
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
        'title': _('Create Supplier Invoice'),
        'submit_text': _('Save Invoice'),
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

            messages.success(request, _('Supplier invoice %(number)s updated.') % {'number': invoice.invoice_number})
            return redirect('erp:supplier_invoice_detail', pk=invoice.pk)
    else:
        form = SupplierInvoiceForm(instance=invoice, company=company)
        formset = SupplierInvoiceLineFormSet(instance=invoice)

    return render(request, 'erp/supplier_invoices/form.html', {
        'form': form,
        'formset': formset,
        'invoice': invoice,
        'title': _('Edit Supplier Invoice: %(number)s') % {'number': invoice.invoice_number},
        'submit_text': _('Save Changes'),
    })


@staff_member_required
def supplier_invoice_approve(request, pk):
    company = get_user_company(request.user)
    supplier_invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)

    if request.method == 'POST':
        if supplier_invoice.status not in ('draft', 'pending'):
            messages.error(request, _('Cannot approve this invoice in its current state.'))
            return redirect('erp:supplier_invoice_detail', pk=supplier_invoice.pk)

        supplier_invoice.status = SupplierInvoice.Status.APPROVED
        supplier_invoice.save(update_fields=['status'])

        from erp.services.inventory_accounting import create_supplier_invoice_journal_entry as _create_grni_clearing_je
        try:
            _create_grni_clearing_je(supplier_invoice, request.user)
        except Exception:
            _logger.exception(
                'Failed to create GRNI-clearing JE for supplier invoice %s',
                supplier_invoice.invoice_number,
            )
            pass  # Non-fatal: log but don't block the approval

        messages.success(request, _('Supplier invoice %(number)s approved.') % {'number': supplier_invoice.invoice_number})
        return redirect('erp:supplier_invoice_detail', pk=supplier_invoice.pk)

    return render(request, 'erp/supplier_invoices/detail.html', {
        'invoice': supplier_invoice,
        'lines': supplier_invoice.lines.select_related('tax_rate', 'account').all(),
        'payments': supplier_invoice.payment_allocations.select_related('payment').all(),
    })


@staff_member_required
def supplier_invoice_delete(request, pk):
    company = get_user_company(request.user)
    invoice = get_object_or_404(SupplierInvoice, pk=pk, company=company)

    if request.method == 'POST':
        with transaction.atomic():
            number = invoice.invoice_number
            # Reverse and cancel all posted journal entries linked to this supplier invoice
            for je in JournalEntry.objects.filter(
                company=company,
                reference=number,
                status=JournalEntry.Status.POSTED,
            ):
                account_ids = sorted(je.lines.values_list('account_id', flat=True))
                locked_accounts = {
                    a.pk: a for a in Account.objects.select_for_update().filter(pk__in=account_ids)
                }
                for line in je.lines.select_related('account').all():
                    acc = locked_accounts[line.account_id]
                    acc.update_balance(line.credit_amount, line.debit_amount)
                    acc.save(update_fields=['current_balance'])
                je.status = JournalEntry.Status.CANCELLED
                je.save(update_fields=['status'])
            invoice.delete()
        messages.success(request, _('Supplier invoice %(number)s deleted.') % {'number': number})
        return redirect('erp:supplier_invoice_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': invoice,
        'object_type': 'فاتورة مورد',
        'cancel_url': reverse('erp:supplier_invoice_detail', args=[pk]),
    })


# ── Supplier Payments ───────────────────────────────────────────────────────

@staff_member_required
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
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

    payments, current_sort, current_order = apply_sorting(
        request, payments,
        allowed_fields=['payment_number', 'payment_date', 'amount'],
        default='-payment_date',
    )
    page_obj, query_string = paginate_qs(request, payments)

    return render(request, 'erp/supplier_payments/list.html', {
        'payments': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'stats': stats,
        'suppliers': suppliers,
        'selected_supplier': supplier_filter or '',
        'current_sort': current_sort,
        'current_order': current_order,
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
                _logger.exception('Failed to create journal entry for supplier payment %s', payment.payment_number)
                messages.warning(request, 'تحذير: تعذّر إنشاء القيد المحاسبي تلقائياً. يُرجى إنشاؤه يدوياً.')

            messages.success(request, _('Supplier payment %(number)s recorded.') % {'number': payment.payment_number})
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
        'title': _('Record Supplier Payment'),
        'submit_text': _('Save Payment'),
    })


@staff_member_required
def supplier_payment_delete(request, pk):
    company = get_user_company(request.user)
    payment = get_object_or_404(SupplierPayment, pk=pk, company=company)

    if request.method == 'POST':
        with transaction.atomic():
            # Reverse allocations before deletion
            for alloc in payment.allocations.all():
                inv = alloc.invoice
                inv.paid_amount -= alloc.amount
                inv.calculate_totals()
                inv.save()

            number = payment.payment_number
            # Reverse and cancel all posted journal entries linked to this payment
            for je in JournalEntry.objects.filter(
                company=company,
                reference=number,
                status=JournalEntry.Status.POSTED,
            ):
                account_ids = sorted(je.lines.values_list('account_id', flat=True))
                locked_accounts = {
                    a.pk: a for a in Account.objects.select_for_update().filter(pk__in=account_ids)
                }
                for line in je.lines.select_related('account').all():
                    acc = locked_accounts[line.account_id]
                    acc.update_balance(line.credit_amount, line.debit_amount)
                    acc.save(update_fields=['current_balance'])
                je.status = JournalEntry.Status.CANCELLED
                je.save(update_fields=['status'])
            payment.delete()
        messages.success(request, _('Supplier payment %(number)s deleted.') % {'number': number})
        return redirect('erp:supplier_payment_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': payment,
        'object_type': 'دفعة مورد',
        'cancel_url': reverse('erp:supplier_payment_detail', args=[pk]),
    })
