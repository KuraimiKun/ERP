"""Point-of-Sale (POS) endpoints — terminals, sessions, orders, stats."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce, ExtractHour
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from rest_framework.decorators import api_view
from rest_framework.response import Response

from erp.models import (
    Customer,
    PaymentMethod,
    POSOrder,
    POSOrderLine,
    POSPayment,
    POSSession,
    POSTerminal,
    Product,
    ProductCategory,
)

from ..base import _error, _get_employee


# ───────────────────────────────────────────────────────────────────────
# Terminals & Sessions
# ───────────────────────────────────────────────────────────────────────


@api_view(["GET"])
def mobile_pos_terminals(request):
    """List available POS terminals for this employee."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    terminals = POSTerminal.objects.filter(
        company=employee.company,
        is_active=True,
    )

    result = []
    for t in terminals:
        if not t.allowed_employees.exists() or t.allowed_employees.filter(pk=employee.pk).exists():
            open_session = POSSession.objects.filter(terminal=t, status="open").first()
            result.append(
                {
                    "id": t.pk,
                    "code": t.code,
                    "name": t.name,
                    "name_ar": t.name_ar or "",
                    "location": t.location or "",
                    "has_open_session": open_session is not None,
                    "open_session_id": open_session.pk if open_session else None,
                    "open_session_number": open_session.session_number if open_session else None,
                }
            )

    return Response({"terminals": result})


@api_view(["POST"])
def mobile_pos_session_open(request):
    """Open a new POS session."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    terminal_id = request.data.get("terminal_id")
    opening_balance = request.data.get("opening_balance", "0")

    try:
        terminal = POSTerminal.objects.get(
            pk=terminal_id,
            company=employee.company,
            is_active=True,
        )
    except POSTerminal.DoesNotExist:
        return _error("Terminal not found.")

    from erp.services.pos import open_session

    try:
        session = open_session(
            company=employee.company,
            terminal=terminal,
            employee=employee,
            opening_balance=opening_balance,
        )
    except ValueError as e:
        return _error(str(e))

    return Response(
        {
            "success": True,
            "session": {
                "id": session.pk,
                "session_number": session.session_number,
                "terminal_name": terminal.name,
                "opening_balance": str(session.opening_balance),
                "opened_at": session.opened_at.isoformat() if session.opened_at else None,
            },
        },
        status=201,
    )


@api_view(["GET"])
def mobile_pos_session_detail(request, pk):
    """Get session info."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    try:
        session = POSSession.objects.select_related("terminal").get(
            pk=pk,
            company=employee.company,
        )
    except POSSession.DoesNotExist:
        return _error("Session not found.", 404)

    session.calculate_expected_cash()

    orders = session.orders.filter(status="completed")
    order_count = orders.count()
    total_sales = orders.aggregate(total=Coalesce(Sum("total_amount"), Decimal("0")))["total"]

    return Response(
        {
            "session": {
                "id": session.pk,
                "session_number": session.session_number,
                "terminal_name": session.terminal.name,
                "status": session.status,
                "opening_balance": str(session.opening_balance),
                "expected_cash": str(session.expected_cash),
                "total_sales": str(total_sales),
                "order_count": order_count,
                "opened_at": session.opened_at.isoformat() if session.opened_at else None,
                "closed_at": session.closed_at.isoformat() if session.closed_at else None,
            },
        }
    )


@api_view(["POST"])
def mobile_pos_session_close(request, pk):
    """Close a POS session."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    try:
        session = POSSession.objects.get(
            pk=pk,
            company=employee.company,
            status="open",
        )
    except POSSession.DoesNotExist:
        return _error("Session not found or already closed.", 404)

    closing_balance = request.data.get("closing_balance", "0")
    notes = request.data.get("notes", "")

    from erp.services.pos import close_session

    session = close_session(
        session=session,
        employee=employee,
        closing_balance=closing_balance,
        notes=notes,
    )

    return Response(
        {
            "success": True,
            "session": {
                "id": session.pk,
                "session_number": session.session_number,
                "status": session.status,
                "total_sales": str(session.total_sales),
                "total_orders": session.total_orders,
                "expected_cash": str(session.expected_cash),
                "closing_balance": str(session.closing_balance),
                "cash_difference": str(session.cash_difference),
            },
        }
    )


# ───────────────────────────────────────────────────────────────────────
# Products, Categories, Customers
# ───────────────────────────────────────────────────────────────────────


@api_view(["GET"])
def mobile_pos_products(request):
    """Search products for POS."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    company = employee.company
    q = request.query_params.get("q", "").strip()
    category_id = request.query_params.get("category", "")
    barcode = request.query_params.get("barcode", "").strip()

    products = Product.objects.filter(
        company=company,
        is_active=True,
    ).select_related("category", "tax_rate")

    if barcode:
        products = products.filter(barcode=barcode)
    elif q:
        products = products.filter(
            Q(name__icontains=q) | Q(name_ar__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    products = products[:50]

    return Response(
        {
            "products": [
                {
                    "id": p.pk,
                    "sku": p.sku,
                    "barcode": p.barcode or "",
                    "name": p.name,
                    "name_ar": p.name_ar or "",
                    "selling_price": str(p.selling_price),
                    "cost_price": str(p.cost_price or 0),
                    "min_selling_price": str(p.min_selling_price or 0),
                    "tax_rate_id": p.tax_rate_id,
                    "tax_rate_percent": str(p.tax_rate.rate) if p.tax_rate else "0",
                    "track_inventory": p.track_inventory,
                    "quantity_on_hand": str(p.quantity_on_hand),
                    "image_url": p.image.url if p.image else "",
                    "category_id": p.category_id,
                    "category_name": p.category.name if p.category else "",
                }
                for p in products
            ],
        }
    )


@api_view(["GET"])
def mobile_pos_categories(request):
    """List product categories."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    categories = ProductCategory.objects.filter(
        company=employee.company,
        is_active=True,
    ).order_by("sort_order", "name")

    return Response(
        {
            "categories": [
                {
                    "id": c.pk,
                    "name": c.name,
                    "name_ar": c.name_ar or "",
                    "code": c.code or "",
                }
                for c in categories
            ],
        }
    )


@api_view(["GET"])
def mobile_pos_customers(request):
    """Search customers for POS."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    q = request.query_params.get("q", "").strip()
    customers = Customer.objects.filter(company=employee.company, is_active=True)
    if q:
        customers = customers.filter(
            Q(name__icontains=q) | Q(name_ar__icontains=q) | Q(customer_id__icontains=q) | Q(phone__icontains=q)
        )
    customers = customers[:20]

    return Response(
        {
            "customers": [
                {
                    "id": c.pk,
                    "customer_id": c.customer_id,
                    "name": c.name,
                    "name_ar": c.name_ar or "",
                    "phone": c.phone or "",
                }
                for c in customers
            ],
        }
    )


@api_view(["GET"])
def mobile_pos_payment_methods(request):
    """List payment methods."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    methods = PaymentMethod.objects.filter(
        company=employee.company,
        is_active=True,
    )

    return Response(
        {
            "payment_methods": [
                {
                    "id": m.pk,
                    "name": m.name,
                    "name_ar": m.name_ar if hasattr(m, "name_ar") else "",
                    "code": m.code,
                    "requires_reference": m.requires_reference if hasattr(m, "requires_reference") else False,
                }
                for m in methods
            ],
        }
    )


# ───────────────────────────────────────────────────────────────────────
# Orders
# ───────────────────────────────────────────────────────────────────────


@api_view(["POST"])
def mobile_pos_create_order(request):
    """Create a POS order from cart data."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    session_id = request.data.get("session_id")
    cart_items = request.data.get("items", [])
    customer_id = request.data.get("customer_id")
    discount_percent = Decimal(str(request.data.get("discount_percent", 0)))
    discount_amount = Decimal(str(request.data.get("discount_amount", 0)))
    notes = request.data.get("notes", "")

    if not cart_items:
        return _error("Cart is empty.")

    try:
        session = POSSession.objects.get(
            pk=session_id,
            company=employee.company,
            status="open",
        )
    except POSSession.DoesNotExist:
        return _error("Session not found or closed.")

    customer = None
    if customer_id:
        try:
            customer = Customer.objects.get(pk=customer_id, company=employee.company)
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
        return _error(str(e))

    return Response(
        {
            "success": True,
            "order_id": order.pk,
            "order_number": order.order_number,
            "total_amount": str(order.total_amount),
            "subtotal": str(order.subtotal),
            "tax_amount": str(order.tax_amount),
            "discount_amount": str(order.discount_amount),
        },
        status=201,
    )


@api_view(["POST"])
def mobile_pos_complete_order(request):
    """Process payment and complete order."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    order_id = request.data.get("order_id")
    payments_data = request.data.get("payments", [])

    if not payments_data:
        return _error("No payment data provided.")

    try:
        order = POSOrder.objects.get(
            pk=order_id,
            company=employee.company,
            status="draft",
        )
    except POSOrder.DoesNotExist:
        return _error("Order not found or already completed.")

    from erp.services.pos import complete_pos_order

    try:
        order = complete_pos_order(order=order, payments_data=payments_data)
    except ValueError as e:
        return _error(str(e))

    payments = order.payments.select_related("payment_method").all()

    return Response(
        {
            "success": True,
            "order_id": order.pk,
            "order_number": order.order_number,
            "status": order.status,
            "total_amount": str(order.total_amount),
            "payments": [
                {
                    "method": p.payment_method.name,
                    "method_code": p.payment_method.code,
                    "amount": str(p.amount),
                    "tendered": str(p.tendered),
                    "change": str(p.change_amount),
                }
                for p in payments
            ],
        }
    )


@api_view(["GET"])
def mobile_pos_receipt(request, pk):
    """Get receipt data as JSON."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    try:
        order = POSOrder.objects.select_related(
            "session__terminal",
            "customer",
            "employee",
        ).get(pk=pk, company=employee.company)
    except POSOrder.DoesNotExist:
        return _error("Order not found.", 404)

    lines = order.lines.select_related("product").all()
    payments = order.payments.select_related("payment_method").all()
    terminal = order.session.terminal

    return Response(
        {
            "receipt": {
                "order_number": order.order_number,
                "order_date": order.order_date.isoformat(),
                "status": order.status,
                "terminal_name": terminal.name,
                "receipt_header": terminal.receipt_header or "",
                "receipt_footer": terminal.receipt_footer or "",
                "employee_name": str(order.employee) if order.employee else "",
                "customer_name": order.customer.name if order.customer else "",
                "subtotal": str(order.subtotal),
                "discount_amount": str(order.discount_amount),
                "tax_amount": str(order.tax_amount),
                "total_amount": str(order.total_amount),
                "lines": [
                    {
                        "product_name": l.product_name,
                        "product_sku": l.product_sku,
                        "quantity": str(l.quantity),
                        "unit_price": str(l.unit_price),
                        "discount_percent": str(l.discount_percent),
                        "tax_amount": str(l.tax_amount),
                        "line_total": str(l.line_total),
                    }
                    for l in lines
                ],
                "payments": [
                    {
                        "method": p.payment_method.name,
                        "amount": str(p.amount),
                        "tendered": str(p.tendered),
                        "change": str(p.change_amount),
                    }
                    for p in payments
                ],
                "company_name": employee.company.name,
                "company_name_ar": employee.company.name_ar if hasattr(employee.company, "name_ar") else "",
            },
        }
    )


@api_view(["GET"])
def mobile_pos_order_history(request, session_id):
    """Orders for a session."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    try:
        session = POSSession.objects.get(pk=session_id, company=employee.company)
    except POSSession.DoesNotExist:
        return _error("Session not found.", 404)

    orders = session.orders.select_related("customer", "employee").order_by("-order_date")

    return Response(
        {
            "orders": [
                {
                    "id": o.pk,
                    "order_number": o.order_number,
                    "order_date": o.order_date.isoformat(),
                    "customer_name": o.customer.name if o.customer else "",
                    "total_amount": str(o.total_amount),
                    "status": o.status,
                }
                for o in orders
            ],
        }
    )


# ───────────────────────────────────────────────────────────────────────
# Stats / Performance
# ───────────────────────────────────────────────────────────────────────


@api_view(["GET"])
@cache_page(60 * 5)  # 5 minutes
@vary_on_cookie
def mobile_pos_stats(request):
    """
    Employee POS performance statistics.

    Query params:
        period: today | week | month  (default: today)
    """
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_use_pos:
        return _error("Permission denied.", 403)

    period = request.query_params.get("period", "today")
    today = timezone.now().date()

    if period == "week":
        start_date = today - timedelta(days=today.weekday())
    elif period == "month":
        start_date = today.replace(day=1)
    else:
        start_date = today

    # Base queryset: completed orders by this employee in date range
    orders_qs = POSOrder.objects.filter(
        employee=employee,
        status="completed",
        order_date__date__gte=start_date,
        order_date__date__lte=today,
    )

    # Summary
    summary = orders_qs.aggregate(
        total_sales=Coalesce(Sum("total_amount"), Decimal("0")),
        total_orders=Count("id"),
        average_order=Coalesce(Avg("total_amount"), Decimal("0")),
        total_discount=Coalesce(Sum("discount_amount"), Decimal("0")),
        total_tax=Coalesce(Sum("tax_amount"), Decimal("0")),
    )

    # Items sold
    total_items = POSOrderLine.objects.filter(
        order__in=orders_qs,
    ).aggregate(
        total=Coalesce(Sum("quantity"), Decimal("0")),
    )["total"]

    # Refunds
    refund_qs = POSOrder.objects.filter(
        employee=employee,
        status="refunded",
        order_date__date__gte=start_date,
        order_date__date__lte=today,
    )
    refund_stats = refund_qs.aggregate(
        total_refunds=Coalesce(Sum("total_amount"), Decimal("0")),
        refund_count=Count("id"),
    )

    # Payment breakdown
    payment_breakdown = (
        POSPayment.objects.filter(
            order__in=orders_qs,
        )
        .values(
            "payment_method__name",
            "payment_method__code",
        )
        .annotate(
            total=Sum("amount"),
            count=Count("id"),
        )
        .order_by("-total")
    )

    payment_list = []
    for pb in payment_breakdown:
        payment_list.append(
            {
                "method": pb["payment_method__name"],
                "code": pb["payment_method__code"],
                "total": str(pb["total"]),
                "count": pb["count"],
            }
        )

    # Top products
    top_products = (
        POSOrderLine.objects.filter(
            order__in=orders_qs,
        )
        .values(
            "product__name",
            "product__sku",
        )
        .annotate(
            quantity=Sum("quantity"),
            total=Sum("line_total"),
        )
        .order_by("-total")[:5]
    )

    top_list = [
        {
            "name": tp["product__name"],
            "sku": tp["product__sku"],
            "quantity": str(tp["quantity"]),
            "total": str(tp["total"]),
        }
        for tp in top_products
    ]

    # Recent sessions
    recent_sessions = (
        POSSession.objects.filter(
            opened_by=employee,
        )
        .select_related("terminal")
        .order_by("-opened_at")[:10]
    )

    session_list = [
        {
            "id": s.pk,
            "session_number": s.session_number,
            "terminal_name": s.terminal.name,
            "opened_at": s.opened_at.isoformat() if s.opened_at else None,
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
            "status": s.status,
            "total_sales": str(s.total_sales or 0),
            "total_orders": s.total_orders or 0,
            "cash_difference": str(s.cash_difference or 0),
        }
        for s in recent_sessions
    ]

    # Hourly sales
    hourly = (
        orders_qs.annotate(
            hour=ExtractHour("order_date"),
        )
        .values("hour")
        .annotate(
            total=Sum("total_amount"),
            count=Count("id"),
        )
        .order_by("hour")
    )

    hourly_list = [
        {
            "hour": h["hour"],
            "total": str(h["total"]),
            "count": h["count"],
        }
        for h in hourly
    ]

    return Response(
        {
            "period": period,
            "summary": {
                "total_sales": str(summary["total_sales"]),
                "total_orders": summary["total_orders"],
                "average_order": str(summary["average_order"].quantize(Decimal("0.01"))),
                "total_items_sold": str(total_items),
                "total_discount": str(summary["total_discount"]),
                "total_tax": str(summary["total_tax"]),
                "total_refunds": str(refund_stats["total_refunds"]),
                "refund_count": refund_stats["refund_count"],
            },
            "payment_breakdown": payment_list,
            "top_products": top_list,
            "recent_sessions": session_list,
            "hourly_sales": hourly_list,
        }
    )
