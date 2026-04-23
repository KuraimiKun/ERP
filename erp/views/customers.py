"""
ERP Views – Customers
"""

from django.db.models import Q

from erp.models import Customer
from erp.forms import CustomerForm
from erp.services import get_customer_id
from ._common import (
    render,
    get_object_or_404,
    redirect,
    messages,
    reverse,
    get_user_company,
    staff_member_required,
    paginate_qs,
    apply_sorting,
)


@staff_member_required
def customer_list(request):
    """List all customers."""
    company = get_user_company(request.user)
    customers = Customer.objects.filter(company=company)

    customer_type = request.GET.get("type")
    if customer_type:
        customers = customers.filter(customer_type=customer_type)

    search = request.GET.get("search")
    if search:
        customers = customers.filter(
            Q(name__icontains=search) | Q(email__icontains=search) | Q(customer_id__icontains=search)
        )

    customers, current_sort, current_order = apply_sorting(
        request,
        customers,
        allowed_fields=["name", "email", "customer_type", "created_at"],
        default="name",
    )
    page_obj, query_string = paginate_qs(request, customers)

    return render(
        request,
        "erp/customers/list.html",
        {
            "customers": page_obj,
            "page_obj": page_obj,
            "query_string": query_string,
            "customer_types": Customer.CustomerType.choices,
            "current_sort": current_sort,
            "current_order": current_order,
        },
    )


@staff_member_required
def customer_detail(request, pk):
    """Customer detail view."""
    company = get_user_company(request.user)
    customer = get_object_or_404(Customer, pk=pk, company=company)

    invoices = customer.invoices.select_related("currency").order_by("-invoice_date")[:10]
    payments = customer.payments.select_related("currency", "payment_method").order_by("-payment_date")[:10]
    quotes = customer.quotes.order_by("-quote_date")[:10]
    interactions = customer.interactions.order_by("-interaction_date")[:10]

    return render(
        request,
        "erp/customers/detail.html",
        {
            "customer": customer,
            "invoices": invoices,
            "payments": payments,
            "quotes": quotes,
            "interactions": interactions,
        },
    )


@staff_member_required
def customer_create(request):
    """Create a new customer."""
    company = get_user_company(request.user)

    if request.method == "POST":
        form = CustomerForm(request.POST, company=company)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.company = company
            customer.customer_id = get_customer_id(company)
            customer.save()
            messages.success(request, f'Customer "{customer.name}" created successfully.')
            return redirect("erp:customer_detail", pk=customer.pk)
    else:
        form = CustomerForm(company=company)

    return render(
        request,
        "erp/customers/form.html",
        {
            "form": form,
            "title": "Add Customer",
            "submit_text": "Create Customer",
        },
    )


@staff_member_required
def customer_edit(request, pk):
    """Edit an existing customer."""
    company = get_user_company(request.user)
    customer = get_object_or_404(Customer, pk=pk, company=company)

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Customer "{customer.name}" updated successfully.')
            return redirect("erp:customer_detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer, company=company)

    return render(
        request,
        "erp/customers/form.html",
        {
            "form": form,
            "customer": customer,
            "title": f"Edit Customer: {customer.name}",
            "submit_text": "Save Changes",
        },
    )


@staff_member_required
def customer_delete(request, pk):
    """Delete a customer."""
    company = get_user_company(request.user)
    customer = get_object_or_404(Customer, pk=pk, company=company)

    if request.method == "POST":
        name = customer.name
        customer.delete()
        messages.success(request, f'Customer "{name}" deleted successfully.')
        return redirect("erp:customer_list")

    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": customer,
            "object_type": "Customer",
            "cancel_url": reverse("erp:customer_detail", args=[pk]),
        },
    )
