"""
ERP Views - POS (Point of Sale)

Full-screen POS interface for employees with portal_can_use_pos permission.
Page views return HTML templates; API views return JsonResponse.
"""

import json
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from django.db.models import Q

from erp.models import (
    POSTerminal, POSSession, POSOrder,
    Product, ProductCategory, Customer, PaymentMethod,
)
from erp.decorators import employee_or_owner_required, portal_permission_required
from ._common import render, redirect, messages, get_user_company, paginate_qs
from ._common import staff_member_required
from .employee_portal import _get_employee_for_user, _portal_context, _no_employee


# ═══════════════════════════════════════════════════════════════════════════
# Page Views (HTML)
# ═══════════════════════════════════════════════════════════════════════════

@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
def pos_terminal_select(request):
    """Choose a POS terminal and optionally open/resume a session."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    company = get_user_company(request.user)
    terminals = POSTerminal.objects.filter(company=company, is_active=True)

    # Filter by allowed_employees (if populated)
    accessible = []
    for t in terminals:
        if not t.allowed_employees.exists() or t.allowed_employees.filter(pk=employee.pk).exists():
            t.open_session = POSSession.objects.filter(terminal=t, status='open').first()
            accessible.append(t)

    ctx = _portal_context(employee)
    ctx['terminals'] = accessible
    return render(request, 'erp/pos/pos_terminal_select.html', ctx)


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
@require_POST
def pos_session_open(request):
    """Open a new session on a terminal."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    terminal_id = request.POST.get('terminal_id')
    opening_balance = request.POST.get('opening_balance', '0')

    company = get_user_company(request.user)

    try:
        terminal = POSTerminal.objects.get(pk=terminal_id, company=company, is_active=True)
    except POSTerminal.DoesNotExist:
        messages.error(request, 'Terminal not found.')
        return redirect('erp:pos_terminal_select')

    from erp.services.pos import open_session
    try:
        session = open_session(
            company=company,
            terminal=terminal,
            employee=employee,
            opening_balance=opening_balance,
        )
        return redirect('erp:pos_main', session_id=session.pk)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('erp:pos_terminal_select')


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
def pos_main(request, session_id):
    """Main full-screen POS interface."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    company = get_user_company(request.user)
    try:
        session = POSSession.objects.select_related(
            'terminal', 'terminal__warehouse', 'opened_by',
        ).get(pk=session_id, company=company, status='open')
    except POSSession.DoesNotExist:
        messages.error(request, 'Session not found or already closed.')
        return redirect('erp:pos_terminal_select')

    payment_methods = list(
        PaymentMethod.objects.filter(company=company, is_active=True)
        .values('id', 'name', 'name_ar', 'code', 'requires_reference')
    )
    categories = list(
        ProductCategory.objects.filter(company=company, is_active=True)
        .order_by('sort_order', 'name')
        .values('id', 'name', 'name_ar')
    )

    ctx = {
        'session': session,
        'terminal': session.terminal,
        'employee': employee,
        'payment_methods_json': json.dumps(payment_methods),
        'categories_json': json.dumps(categories),
        'company': company,
    }
    return render(request, 'erp/pos/pos_main.html', ctx)


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
def pos_session_close(request, session_id):
    """Close session form and processing."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    company = get_user_company(request.user)
    try:
        session = POSSession.objects.select_related('terminal').get(
            pk=session_id, company=company, status='open',
        )
    except POSSession.DoesNotExist:
        messages.error(request, 'Session not found or already closed.')
        return redirect('erp:pos_terminal_select')

    if request.method == 'POST':
        closing_balance = request.POST.get('closing_balance', '0')
        notes = request.POST.get('notes', '')

        from erp.services.pos import close_session
        session = close_session(
            session=session,
            employee=employee,
            closing_balance=closing_balance,
            notes=notes,
        )
        messages.success(request, f'Session {session.session_number} closed successfully.')
        return redirect('erp:pos_terminal_select')

    # GET: show the close form with session summary
    session.calculate_expected_cash()
    orders = session.orders.filter(status='completed')

    ctx = _portal_context(employee)
    ctx.update({
        'session': session,
        'orders': orders,
        'order_count': orders.count(),
    })
    return render(request, 'erp/pos/pos_session_close.html', ctx)


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
def pos_order_history(request, session_id):
    """List past orders for a session."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    company = get_user_company(request.user)
    try:
        session = POSSession.objects.select_related('terminal').get(
            pk=session_id, company=company,
        )
    except POSSession.DoesNotExist:
        messages.error(request, 'Session not found.')
        return redirect('erp:pos_terminal_select')

    orders = session.orders.select_related('customer', 'employee').order_by('-order_date')

    ctx = _portal_context(employee)
    ctx.update({'session': session, 'orders': orders})
    return render(request, 'erp/pos/pos_order_history.html', ctx)


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
def pos_order_receipt(request, order_id):
    """Print-friendly receipt view."""
    employee = _get_employee_for_user(request)
    if not employee:
        return _no_employee(request)

    company = get_user_company(request.user)
    try:
        order = POSOrder.objects.select_related(
            'session__terminal', 'customer', 'employee',
        ).get(pk=order_id, company=company)
    except POSOrder.DoesNotExist:
        messages.error(request, 'Order not found.')
        return redirect('erp:pos_terminal_select')

    lines = order.lines.select_related('product').all()
    payments = order.payments.select_related('payment_method').all()

    ctx = {
        'order': order,
        'lines': lines,
        'payments': payments,
        'company': company,
        'terminal': order.session.terminal,
    }
    return render(request, 'erp/pos/pos_receipt.html', ctx)


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
@require_POST
def pos_generate_invoice(request, order_id):
    """Generate an Invoice from a POS order. Returns JSON."""
    employee = _get_employee_for_user(request)
    if not employee:
        return JsonResponse({'error': 'No employee profile'}, status=400)

    company = get_user_company(request.user)
    try:
        order = POSOrder.objects.get(pk=order_id, company=company)
    except POSOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)

    from erp.services.pos import generate_invoice_from_pos
    try:
        invoice = generate_invoice_from_pos(order, request.user)
        return JsonResponse({
            'success': True,
            'invoice_id': invoice.pk,
            'invoice_number': invoice.invoice_number,
        })
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
# API Views (JSON) -- called from the POS frontend JS
# ═══════════════════════════════════════════════════════════════════════════

@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
@require_GET
def pos_api_products(request):
    """Search products by barcode, name, SKU, or category."""
    company = get_user_company(request.user)
    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    barcode = request.GET.get('barcode', '').strip()

    products = Product.objects.filter(
        company=company, is_active=True,
    ).select_related('category', 'tax_rate')

    if barcode:
        products = products.filter(barcode=barcode)
    elif q:
        products = products.filter(
            Q(name__icontains=q) | Q(name_ar__icontains=q) |
            Q(sku__icontains=q) | Q(barcode__icontains=q)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    products = products[:50]

    data = []
    for p in products:
        data.append({
            'id': p.pk,
            'sku': p.sku,
            'barcode': p.barcode or '',
            'name': p.name,
            'name_ar': p.name_ar or '',
            'selling_price': str(p.selling_price),
            'cost_price': str(p.cost_price or 0),
            'min_selling_price': str(p.min_selling_price or 0),
            'tax_rate_id': p.tax_rate_id,
            'tax_rate_percent': str(p.tax_rate.rate) if p.tax_rate else '0',
            'track_inventory': p.track_inventory,
            'quantity_on_hand': str(p.quantity_on_hand),
            'image_url': p.image.url if p.image else '',
            'category_id': p.category_id,
            'category_name': p.category.name if p.category else '',
        })

    return JsonResponse({'products': data})


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
@require_GET
def pos_api_categories(request):
    """Return all active product categories."""
    company = get_user_company(request.user)
    categories = ProductCategory.objects.filter(
        company=company, is_active=True,
    ).order_by('sort_order', 'name')

    data = [{'id': c.pk, 'name': c.name, 'name_ar': c.name_ar or ''} for c in categories]
    return JsonResponse({'categories': data})


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
@require_GET
def pos_api_customers(request):
    """Search customers by name, ID, or phone."""
    company = get_user_company(request.user)
    q = request.GET.get('q', '').strip()

    customers = Customer.objects.filter(company=company, is_active=True)
    if q:
        customers = customers.filter(
            Q(name__icontains=q) | Q(name_ar__icontains=q) |
            Q(customer_id__icontains=q) | Q(phone__icontains=q)
        )
    customers = customers[:20]

    data = [{
        'id': c.pk,
        'customer_id': c.customer_id,
        'name': c.name,
        'name_ar': c.name_ar or '',
        'phone': c.phone or '',
    } for c in customers]

    return JsonResponse({'customers': data})


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
@require_POST
def pos_api_create_order(request):
    """Create a POS order from cart JSON data."""
    employee = _get_employee_for_user(request)
    if not employee:
        return JsonResponse({'error': 'No employee profile'}, status=400)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    session_id = body.get('session_id')
    cart_items = body.get('items', [])
    customer_id = body.get('customer_id')
    discount_percent = Decimal(str(body.get('discount_percent', 0)))
    discount_amount = Decimal(str(body.get('discount_amount', 0)))
    notes = body.get('notes', '')

    if not cart_items:
        return JsonResponse({'error': 'Cart is empty'}, status=400)

    company = get_user_company(request.user)
    try:
        session = POSSession.objects.get(pk=session_id, company=company, status='open')
    except POSSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found or closed'}, status=400)

    customer = None
    if customer_id:
        try:
            customer = Customer.objects.get(pk=customer_id, company=company)
        except Customer.DoesNotExist:
            pass

    from erp.services.pos import create_pos_order
    try:
        order = create_pos_order(
            session=session,
            employee=employee,
            cart_items=cart_items,
            customer=customer,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            notes=notes,
        )
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({
        'success': True,
        'order_id': order.pk,
        'order_number': order.order_number,
        'total_amount': str(order.total_amount),
        'subtotal': str(order.subtotal),
        'tax_amount': str(order.tax_amount),
        'discount_amount': str(order.discount_amount),
    })


@employee_or_owner_required
@portal_permission_required('portal_can_use_pos')
@require_POST
def pos_api_complete_order(request):
    """Process payment and complete a POS order."""
    employee = _get_employee_for_user(request)
    if not employee:
        return JsonResponse({'error': 'No employee profile'}, status=400)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    order_id = body.get('order_id')
    payments_data = body.get('payments', [])

    if not payments_data:
        return JsonResponse({'error': 'No payment data provided'}, status=400)

    company = get_user_company(request.user)
    try:
        order = POSOrder.objects.get(pk=order_id, company=company, status='draft')
    except POSOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found or already completed'}, status=400)

    from erp.services.pos import complete_pos_order
    try:
        order = complete_pos_order(order=order, payments_data=payments_data)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    # Build response with payment details
    payments = order.payments.select_related('payment_method').all()
    payments_response = [{
        'method': p.payment_method.name,
        'amount': str(p.amount),
        'tendered': str(p.tendered),
        'change': str(p.change_amount),
    } for p in payments]

    return JsonResponse({
        'success': True,
        'order_id': order.pk,
        'order_number': order.order_number,
        'status': order.status,
        'total_amount': str(order.total_amount),
        'payments': payments_response,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Admin / Staff Views (ERP Panel)
# ═══════════════════════════════════════════════════════════════════════════

from django.shortcuts import get_object_or_404
from django.urls import reverse
from erp.forms import POSTerminalForm


@staff_member_required
def pos_terminal_list(request):
    """List all POS terminals."""
    company = get_user_company(request.user)
    qs = POSTerminal.objects.filter(company=company).select_related('warehouse')

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))

    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    page_obj, query_string = paginate_qs(request, qs.order_by('code'))

    return render(request, 'erp/pos/terminal_list.html', {
        'terminals': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'search': search,
        'status_filter': status_filter,
        'total_count': POSTerminal.objects.filter(company=company).count(),
        'active_count': POSTerminal.objects.filter(company=company, is_active=True).count(),
    })


@staff_member_required
def pos_terminal_create(request):
    """Create a new POS terminal."""
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = POSTerminalForm(request.POST, company=company)
        if form.is_valid():
            terminal = form.save(commit=False)
            terminal.company = company
            terminal.save()
            form.save_m2m()
            messages.success(request, f'Terminal "{terminal.name}" created successfully.')
            return redirect('erp:pos_terminal_detail', pk=terminal.pk)
    else:
        form = POSTerminalForm(company=company)

    return render(request, 'erp/pos/terminal_form.html', {
        'form': form,
        'title': 'New POS Terminal',
        'submit_text': 'Create Terminal',
    })


@staff_member_required
def pos_terminal_detail(request, pk):
    """POS terminal detail with recent sessions."""
    company = get_user_company(request.user)
    terminal = get_object_or_404(POSTerminal, pk=pk, company=company)

    sessions = terminal.sessions.select_related('opened_by', 'closed_by').order_by('-opened_at')[:20]

    return render(request, 'erp/pos/terminal_detail.html', {
        'terminal': terminal,
        'sessions': sessions,
        'allowed_employees': terminal.allowed_employees.all(),
    })


@staff_member_required
def pos_terminal_edit(request, pk):
    """Edit a POS terminal."""
    company = get_user_company(request.user)
    terminal = get_object_or_404(POSTerminal, pk=pk, company=company)

    if request.method == 'POST':
        form = POSTerminalForm(request.POST, instance=terminal, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Terminal "{terminal.name}" updated successfully.')
            return redirect('erp:pos_terminal_detail', pk=terminal.pk)
    else:
        form = POSTerminalForm(instance=terminal, company=company)

    return render(request, 'erp/pos/terminal_form.html', {
        'form': form,
        'terminal': terminal,
        'title': f'Edit Terminal: {terminal.code}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def pos_terminal_delete(request, pk):
    """Delete a POS terminal."""
    company = get_user_company(request.user)
    terminal = get_object_or_404(POSTerminal, pk=pk, company=company)

    if request.method == 'POST':
        terminal.delete()
        messages.success(request, f'Terminal "{terminal.name}" deleted.')
        return redirect('erp:pos_terminal_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': terminal,
        'object_type': 'POS Terminal',
        'cancel_url': reverse('erp:pos_terminal_detail', args=[pk]),
    })


@staff_member_required
@cache_page(60 * 5)   # 5 minutes
@vary_on_cookie
def pos_session_list(request):
    """List all POS sessions across terminals."""
    company = get_user_company(request.user)
    qs = POSSession.objects.filter(company=company).select_related(
        'terminal', 'opened_by', 'closed_by',
    )

    terminal_filter = request.GET.get('terminal', '')
    if terminal_filter:
        qs = qs.filter(terminal_id=terminal_filter)

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    page_obj, query_string = paginate_qs(request, qs.order_by('-opened_at'))
    terminals = POSTerminal.objects.filter(company=company).order_by('code')

    return render(request, 'erp/pos/session_list.html', {
        'sessions': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'terminals': terminals,
        'terminal_filter': terminal_filter,
        'status_filter': status_filter,
    })


@staff_member_required
def pos_session_detail_admin(request, pk):
    """Admin view of a POS session with orders."""
    company = get_user_company(request.user)
    session = get_object_or_404(
        POSSession.objects.select_related('terminal', 'opened_by', 'closed_by'),
        pk=pk, company=company,
    )

    orders = session.orders.select_related('customer', 'employee').order_by('-order_date')

    return render(request, 'erp/pos/session_detail.html', {
        'session': session,
        'orders': orders,
    })


@staff_member_required
def pos_order_list(request):
    """List all POS orders."""
    company = get_user_company(request.user)
    qs = POSOrder.objects.filter(company=company).select_related(
        'session__terminal', 'customer', 'employee',
    )

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(order_number__icontains=search) |
            Q(customer__name__icontains=search)
        )

    page_obj, query_string = paginate_qs(request, qs.order_by('-order_date'))

    return render(request, 'erp/pos/order_list.html', {
        'orders': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'status_filter': status_filter,
        'search': search,
    })


@staff_member_required
def pos_order_detail_admin(request, pk):
    """Admin view of a POS order with lines and payments."""
    company = get_user_company(request.user)
    order = get_object_or_404(
        POSOrder.objects.select_related(
            'session__terminal', 'customer', 'employee', 'invoice',
        ),
        pk=pk, company=company,
    )

    lines = order.lines.select_related('product', 'tax_rate').all()
    payments = order.payments.select_related('payment_method').all()

    return render(request, 'erp/pos/order_detail.html', {
        'order': order,
        'lines': lines,
        'payments': payments,
    })
