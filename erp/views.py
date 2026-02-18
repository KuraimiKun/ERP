"""
ERP Views

Dashboard and management views for the ERP system.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncMonth, TruncDate
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    Company, Currency, Department, Branch,
    Employee, LeaveRequest, Attendance,
    Customer, Invoice, Payment, Expense,
    Supplier, PurchaseOrder, SupplierInvoice,
    Lead, Campaign, Task,
    Quote, Account, JournalEntry,
    # Services & Products
    ServiceCategory, ServicePricing, ServicePackage,
    Product, ProductCategory, ProductSupplier,
)

# Import tenant_required decorator and use it as staff_member_required
# This allows multi-tenant users (not just staff) to access ERP views
from .decorators import tenant_required as staff_member_required


def get_user_company(user):
    """Get the company associated with the current user."""
    # Try to get from employee profile
    if hasattr(user, 'employee_profile') and user.employee_profile:
        return user.employee_profile.company
    # Return first company as fallback
    return Company.objects.first()


@staff_member_required
def dashboard(request):
    """Main ERP dashboard view."""
    company = get_user_company(request.user)
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)
    
    context = {
        'company': company,
        'today': today,
    }
    
    if company:
        # Revenue metrics
        monthly_revenue = Invoice.objects.filter(
            company=company,
            invoice_date__gte=start_of_month,
            status__in=['sent', 'partial', 'paid']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        yearly_revenue = Invoice.objects.filter(
            company=company,
            invoice_date__gte=start_of_year,
            status__in=['sent', 'partial', 'paid']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Outstanding receivables
        outstanding_receivables = Invoice.objects.filter(
            company=company,
            status__in=['sent', 'partial', 'overdue']
        ).aggregate(total=Sum('balance_due'))['total'] or Decimal('0')
        
        # Overdue invoices
        overdue_invoices = Invoice.objects.filter(
            company=company,
            status='overdue'
        ).count()
        
        # Monthly expenses
        monthly_expenses = Expense.objects.filter(
            company=company,
            expense_date__gte=start_of_month,
            status='approved'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Customer metrics
        total_customers = Customer.objects.filter(company=company, is_active=True).count()
        new_customers_month = Customer.objects.filter(
            company=company,
            created_at__gte=start_of_month
        ).count()
        
        # Lead metrics
        total_leads = Lead.objects.filter(company=company).exclude(status__in=['won', 'lost']).count()
        new_leads_month = Lead.objects.filter(
            company=company,
            created_at__gte=start_of_month
        ).count()
        
        # Quote metrics
        pending_quotes = Quote.objects.filter(
            company=company,
            status__in=['draft', 'sent', 'viewed']
        ).count()
        quotes_value = Quote.objects.filter(
            company=company,
            status__in=['draft', 'sent', 'viewed']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Employee metrics
        total_employees = Employee.objects.filter(company=company, employment_status='active').count()
        pending_leave_requests = LeaveRequest.objects.filter(
            employee__company=company,
            status='pending'
        ).count()
        
        # Task metrics
        pending_tasks = Task.objects.filter(
            company=company,
            status__in=['todo', 'in_progress']
        ).count()
        overdue_tasks = Task.objects.filter(
            company=company,
            status__in=['todo', 'in_progress'],
            due_date__lt=timezone.now()
        ).count()
        
        # Recent invoices
        recent_invoices = Invoice.objects.filter(
            company=company
        ).select_related('customer').order_by('-invoice_date')[:5]
        
        # Recent payments
        recent_payments = Payment.objects.filter(
            company=company
        ).select_related('customer').order_by('-payment_date')[:5]
        
        # Pending tasks
        upcoming_tasks = Task.objects.filter(
            company=company,
            status__in=['todo', 'in_progress']
        ).order_by('due_date')[:5]
        
        # New leads
        recent_leads = Lead.objects.filter(
            company=company
        ).order_by('-created_at')[:5]
        
        context.update({
            'monthly_revenue': monthly_revenue,
            'yearly_revenue': yearly_revenue,
            'outstanding_receivables': outstanding_receivables,
            'overdue_invoices': overdue_invoices,
            'monthly_expenses': monthly_expenses,
            'total_customers': total_customers,
            'new_customers_month': new_customers_month,
            'total_leads': total_leads,
            'new_leads_month': new_leads_month,
            'pending_quotes': pending_quotes,
            'quotes_value': quotes_value,
            'total_employees': total_employees,
            'pending_leave_requests': pending_leave_requests,
            'pending_tasks': pending_tasks,
            'overdue_tasks': overdue_tasks,
            'recent_invoices': recent_invoices,
            'recent_payments': recent_payments,
            'upcoming_tasks': upcoming_tasks,
            'recent_leads': recent_leads,
        })
    
    return render(request, 'erp/dashboard.html', context)


@staff_member_required
def dashboard_charts_data(request):
    """API endpoint for dashboard chart data."""
    company = get_user_company(request.user)
    today = timezone.now().date()
    
    # Last 6 months revenue
    six_months_ago = today - timedelta(days=180)
    monthly_revenue = Invoice.objects.filter(
        company=company,
        invoice_date__gte=six_months_ago,
        status__in=['sent', 'partial', 'paid']
    ).annotate(
        month=TruncMonth('invoice_date')
    ).values('month').annotate(
        total=Sum('total_amount')
    ).order_by('month')
    
    # Revenue by status
    revenue_by_status = Invoice.objects.filter(
        company=company,
        invoice_date__gte=six_months_ago
    ).values('status').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    )
    
    # Leads by source
    leads_by_source = Lead.objects.filter(
        company=company
    ).values('source').annotate(
        count=Count('id')
    )
    
    # Expenses by category
    expenses_by_category = Expense.objects.filter(
        company=company,
        expense_date__gte=six_months_ago,
        status='approved'
    ).values('category__name').annotate(
        total=Sum('total_amount')
    ).order_by('-total')[:10]
    
    return JsonResponse({
        'monthly_revenue': list(monthly_revenue),
        'revenue_by_status': list(revenue_by_status),
        'leads_by_source': list(leads_by_source),
        'expenses_by_category': list(expenses_by_category),
    })


# =============================================================================
# Customer Views
# =============================================================================

@staff_member_required
def customer_list(request):
    """List all customers."""
    company = get_user_company(request.user)
    customers = Customer.objects.filter(company=company).order_by('name')
    
    # Filters
    customer_type = request.GET.get('type')
    if customer_type:
        customers = customers.filter(customer_type=customer_type)
    
    search = request.GET.get('search')
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(email__icontains=search) |
            Q(customer_id__icontains=search)
        )
    
    return render(request, 'erp/customers/list.html', {
        'customers': customers,
        'customer_types': Customer.CustomerType.choices,
    })


@staff_member_required
def customer_detail(request, pk):
    """Customer detail view."""
    company = get_user_company(request.user)
    customer = get_object_or_404(Customer, pk=pk, company=company)
    
    # Get related data
    invoices = customer.invoices.order_by('-invoice_date')[:10]
    payments = customer.payments.order_by('-payment_date')[:10]
    quotes = customer.quotes.order_by('-quote_date')[:10]
    interactions = customer.interactions.order_by('-interaction_date')[:10]
    
    return render(request, 'erp/customers/detail.html', {
        'customer': customer,
        'invoices': invoices,
        'payments': payments,
        'quotes': quotes,
        'interactions': interactions,
    })


# =============================================================================
# Invoice Views
# =============================================================================

@staff_member_required
def invoice_list(request):
    """List all invoices."""
    company = get_user_company(request.user)
    invoices = Invoice.objects.filter(company=company).select_related('customer').order_by('-invoice_date')
    
    # Filters
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    
    search = request.GET.get('search')
    if search:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search) |
            Q(customer__name__icontains=search)
        )
    
    return render(request, 'erp/invoices/list.html', {
        'invoices': invoices,
        'statuses': Invoice.Status.choices,
    })


@staff_member_required
def invoice_detail(request, pk):
    """Invoice detail view."""
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    
    return render(request, 'erp/invoices/detail.html', {
        'invoice': invoice,
        'lines': invoice.lines.all(),
        'payments': invoice.payment_allocations.select_related('payment').all(),
    })


# =============================================================================
# Lead Views
# =============================================================================

@staff_member_required
def lead_list(request):
    """List all leads."""
    company = get_user_company(request.user)
    leads = Lead.objects.filter(company=company).order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    if status:
        leads = leads.filter(status=status)
    
    source = request.GET.get('source')
    if source:
        leads = leads.filter(source=source)
    
    search = request.GET.get('search')
    if search:
        leads = leads.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(lead_number__icontains=search)
        )
    
    return render(request, 'erp/leads/list.html', {
        'leads': leads,
        'statuses': Lead.Status.choices,
        'sources': Lead.Source.choices,
    })


@staff_member_required
def lead_detail(request, pk):
    """Lead detail view."""
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)
    
    return render(request, 'erp/leads/detail.html', {
        'lead': lead,
        'activities': lead.activities.order_by('-activity_date'),
        'quotes': lead.quotes.order_by('-quote_date'),
    })


# =============================================================================
# Employee Views
# =============================================================================

@staff_member_required
def employee_list(request):
    """List all employees."""
    company = get_user_company(request.user)
    employees = Employee.objects.filter(company=company).select_related('department').order_by('first_name')
    
    # Filters
    department = request.GET.get('department')
    if department:
        employees = employees.filter(department_id=department)
    
    status = request.GET.get('status')
    if status:
        employees = employees.filter(employment_status=status)
    
    search = request.GET.get('search')
    if search:
        employees = employees.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(employee_id__icontains=search)
        )
    
    departments = Department.objects.filter(company=company, is_active=True)
    
    return render(request, 'erp/employees/list.html', {
        'employees': employees,
        'departments': departments,
        'statuses': Employee.EmploymentStatus.choices,
    })


@staff_member_required
def employee_detail(request, pk):
    """Employee detail view."""
    company = get_user_company(request.user)
    employee = get_object_or_404(Employee, pk=pk, company=company)
    
    return render(request, 'erp/employees/detail.html', {
        'employee': employee,
        'documents': employee.documents.order_by('-created_at'),
        'leave_requests': employee.leave_requests.order_by('-created_at')[:10],
        'attendances': employee.attendances.order_by('-date')[:30],
    })


# =============================================================================
# Supplier Views
# =============================================================================

@staff_member_required
def supplier_list(request):
    """List all suppliers."""
    company = get_user_company(request.user)
    suppliers = Supplier.objects.filter(company=company).order_by('name')
    
    # Filters
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
    """Supplier detail view."""
    company = get_user_company(request.user)
    supplier = get_object_or_404(Supplier, pk=pk, company=company)
    
    return render(request, 'erp/suppliers/detail.html', {
        'supplier': supplier,
        'purchase_orders': supplier.purchase_orders.order_by('-po_date')[:10],
        'invoices': supplier.invoices.order_by('-invoice_date')[:10],
        'contacts': supplier.contacts.all(),
        'documents': supplier.documents.order_by('-created_at'),
    })


# =============================================================================
# Task Views
# =============================================================================

@staff_member_required
def task_list(request):
    """List all tasks."""
    company = get_user_company(request.user)
    tasks = Task.objects.filter(company=company).select_related('assigned_to').order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    if status:
        tasks = tasks.filter(status=status)
    
    priority = request.GET.get('priority')
    if priority:
        tasks = tasks.filter(priority=priority)
    
    # Filter by assigned to current user
    my_tasks = request.GET.get('my_tasks')
    if my_tasks and hasattr(request.user, 'employee_profile'):
        tasks = tasks.filter(assigned_to=request.user.employee_profile)
    
    return render(request, 'erp/tasks/list.html', {
        'tasks': tasks,
        'statuses': Task.Status.choices,
        'priorities': Task.Priority.choices,
    })


@staff_member_required
def task_detail(request, pk):
    """Task detail view."""
    company = get_user_company(request.user)
    task = get_object_or_404(Task, pk=pk, company=company)
    
    return render(request, 'erp/tasks/detail.html', {
        'task': task,
        'comments': task.comments.select_related('author').order_by('created_at'),
    })


# =============================================================================
# CRUD Views - Create, Update, Delete
# =============================================================================

from django.contrib import messages
from django.urls import reverse

from .forms import (
    CustomerForm, InvoiceForm, InvoiceLineFormSet,
    LeadForm, LeadActivityForm,
    EmployeeForm, TaskForm, TaskCommentForm,
    SupplierForm, SupplierContactFormSet,
    ExpenseForm, PaymentForm,
    QuoteForm, QuoteLineFormSet,
    JournalEntryForm, JournalEntryLineFormSet,
    # Services & Products
    ServiceCategoryForm, ServicePricingForm,
    ProductCategoryForm, ProductForm, ProductSupplierFormSet,
)


# -----------------------------------------------------------------------------
# Customer CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def customer_create(request):
    """Create a new customer."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = CustomerForm(request.POST, company=company)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.company = company
            customer.save()
            messages.success(request, f'Customer "{customer.name}" created successfully.')
            return redirect('erp:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(company=company)
    
    return render(request, 'erp/customers/form.html', {
        'form': form,
        'title': 'Add Customer',
        'submit_text': 'Create Customer',
    })


@staff_member_required
def customer_edit(request, pk):
    """Edit an existing customer."""
    company = get_user_company(request.user)
    customer = get_object_or_404(Customer, pk=pk, company=company)
    
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Customer "{customer.name}" updated successfully.')
            return redirect('erp:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer, company=company)
    
    return render(request, 'erp/customers/form.html', {
        'form': form,
        'customer': customer,
        'title': f'Edit Customer: {customer.name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def customer_delete(request, pk):
    """Delete a customer."""
    company = get_user_company(request.user)
    customer = get_object_or_404(Customer, pk=pk, company=company)
    
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f'Customer "{name}" deleted successfully.')
        return redirect('erp:customer_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': customer,
        'object_type': 'Customer',
        'cancel_url': reverse('erp:customer_detail', args=[pk]),
    })


# -----------------------------------------------------------------------------
# Invoice CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def invoice_create(request):
    """Create a new invoice."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, company=company)
        formset = InvoiceLineFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.company = company
            invoice.save()
            
            formset.instance = invoice
            formset.save()
            
            # Recalculate totals
            invoice.calculate_totals()
            
            messages.success(request, f'Invoice {invoice.invoice_number} created successfully.')
            return redirect('erp:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(company=company)
        formset = InvoiceLineFormSet()
    
    return render(request, 'erp/invoices/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Create Invoice',
        'submit_text': 'Create Invoice',
    })


@staff_member_required
def invoice_edit(request, pk):
    """Edit an existing invoice."""
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice, company=company)
        formset = InvoiceLineFormSet(request.POST, instance=invoice)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Recalculate totals
            invoice.calculate_totals()
            
            messages.success(request, f'Invoice {invoice.invoice_number} updated successfully.')
            return redirect('erp:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice, company=company)
        formset = InvoiceLineFormSet(instance=invoice)
    
    return render(request, 'erp/invoices/form.html', {
        'form': form,
        'formset': formset,
        'invoice': invoice,
        'title': f'Edit Invoice: {invoice.invoice_number}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def invoice_delete(request, pk):
    """Delete an invoice."""
    company = get_user_company(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    
    if request.method == 'POST':
        number = invoice.invoice_number
        invoice.delete()
        messages.success(request, f'Invoice {number} deleted successfully.')
        return redirect('erp:invoice_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': invoice,
        'object_type': 'Invoice',
        'cancel_url': reverse('erp:invoice_detail', args=[pk]),
    })


# -----------------------------------------------------------------------------
# Lead CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def lead_create(request):
    """Create a new lead."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = LeadForm(request.POST, company=company)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.company = company
            lead.save()
            messages.success(request, f'Lead "{lead.full_name}" created successfully.')
            return redirect('erp:lead_detail', pk=lead.pk)
    else:
        form = LeadForm(company=company)
    
    return render(request, 'erp/leads/form.html', {
        'form': form,
        'title': 'Add Lead',
        'submit_text': 'Create Lead',
    })


@staff_member_required
def lead_edit(request, pk):
    """Edit an existing lead."""
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)
    
    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Lead "{lead.full_name}" updated successfully.')
            return redirect('erp:lead_detail', pk=lead.pk)
    else:
        form = LeadForm(instance=lead, company=company)
    
    return render(request, 'erp/leads/form.html', {
        'form': form,
        'lead': lead,
        'title': f'Edit Lead: {lead.full_name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def lead_delete(request, pk):
    """Delete a lead."""
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)
    
    if request.method == 'POST':
        name = lead.full_name
        lead.delete()
        messages.success(request, f'Lead "{name}" deleted successfully.')
        return redirect('erp:lead_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': lead,
        'object_type': 'Lead',
        'cancel_url': reverse('erp:lead_detail', args=[pk]),
    })


@staff_member_required
def lead_add_activity(request, pk):
    """Add activity to a lead."""
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)
    
    if request.method == 'POST':
        form = LeadActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.lead = lead
            activity.performed_by = request.user
            activity.save()
            messages.success(request, 'Activity added successfully.')
            return redirect('erp:lead_detail', pk=lead.pk)
    else:
        form = LeadActivityForm()
    
    return render(request, 'erp/leads/activity_form.html', {
        'form': form,
        'lead': lead,
        'title': f'Add Activity for {lead.full_name}',
    })


# -----------------------------------------------------------------------------
# Employee CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def employee_create(request):
    """Create a new employee."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.company = company
            employee.save()
            messages.success(request, f'Employee "{employee.full_name}" created successfully.')
            return redirect('erp:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(company=company)
    
    return render(request, 'erp/employees/form.html', {
        'form': form,
        'title': 'Add Employee',
        'submit_text': 'Create Employee',
    })


@staff_member_required
def employee_edit(request, pk):
    """Edit an existing employee."""
    company = get_user_company(request.user)
    employee = get_object_or_404(Employee, pk=pk, company=company)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Employee "{employee.full_name}" updated successfully.')
            return redirect('erp:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee, company=company)
    
    return render(request, 'erp/employees/form.html', {
        'form': form,
        'employee': employee,
        'title': f'Edit Employee: {employee.full_name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def employee_delete(request, pk):
    """Delete an employee."""
    company = get_user_company(request.user)
    employee = get_object_or_404(Employee, pk=pk, company=company)
    
    if request.method == 'POST':
        name = employee.full_name
        employee.delete()
        messages.success(request, f'Employee "{name}" deleted successfully.')
        return redirect('erp:employee_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': employee,
        'object_type': 'Employee',
        'cancel_url': reverse('erp:employee_detail', args=[pk]),
    })


# -----------------------------------------------------------------------------
# Supplier CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def supplier_create(request):
    """Create a new supplier."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = SupplierForm(request.POST, company=company)
        formset = SupplierContactFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            supplier = form.save(commit=False)
            supplier.company = company
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
    """Edit an existing supplier."""
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
    """Delete a supplier."""
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


# -----------------------------------------------------------------------------
# Task CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def task_create(request):
    """Create a new task."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, company=company)
        if form.is_valid():
            task = form.save(commit=False)
            task.company = company
            task.created_by = request.user
            task.save()
            messages.success(request, f'Task "{task.title}" created successfully.')
            return redirect('erp:task_detail', pk=task.pk)
    else:
        form = TaskForm(company=company)
    
    return render(request, 'erp/tasks/form.html', {
        'form': form,
        'title': 'Add Task',
        'submit_text': 'Create Task',
    })


@staff_member_required
def task_edit(request, pk):
    """Edit an existing task."""
    company = get_user_company(request.user)
    task = get_object_or_404(Task, pk=pk, company=company)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Task "{task.title}" updated successfully.')
            return redirect('erp:task_detail', pk=task.pk)
    else:
        form = TaskForm(instance=task, company=company)
    
    return render(request, 'erp/tasks/form.html', {
        'form': form,
        'task': task,
        'title': f'Edit Task: {task.title}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def task_delete(request, pk):
    """Delete a task."""
    company = get_user_company(request.user)
    task = get_object_or_404(Task, pk=pk, company=company)
    
    if request.method == 'POST':
        title = task.title
        task.delete()
        messages.success(request, f'Task "{title}" deleted successfully.')
        return redirect('erp:task_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': task,
        'object_type': 'Task',
        'cancel_url': reverse('erp:task_detail', args=[pk]),
    })


@staff_member_required
def task_add_comment(request, pk):
    """Add comment to a task."""
    company = get_user_company(request.user)
    task = get_object_or_404(Task, pk=pk, company=company)
    
    if request.method == 'POST':
        form = TaskCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            messages.success(request, 'Comment added successfully.')
            return redirect('erp:task_detail', pk=task.pk)
    
    return redirect('erp:task_detail', pk=task.pk)


# -----------------------------------------------------------------------------
# Expense CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def expense_list(request):
    """List all expenses."""
    company = get_user_company(request.user)
    expenses = Expense.objects.filter(company=company).select_related('category', 'employee', 'created_by')
    
    # Filters
    status = request.GET.get('status')
    if status:
        expenses = expenses.filter(status=status)
    
    return render(request, 'erp/expenses/list.html', {
        'expenses': expenses.order_by('-expense_date')[:100],
        'statuses': Expense.Status.choices,
    })


@staff_member_required
def expense_create(request):
    """Create a new expense."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.company = company
            expense.created_by = request.user
            expense.save()
            messages.success(request, 'Expense submitted successfully.')
            return redirect('erp:expense_list')
    else:
        form = ExpenseForm(company=company)
    
    return render(request, 'erp/expenses/form.html', {
        'form': form,
        'title': 'Submit Expense',
        'submit_text': 'Submit Expense',
    })


@staff_member_required
def expense_edit(request, pk):
    """Edit an existing expense."""
    company = get_user_company(request.user)
    expense = get_object_or_404(Expense, pk=pk, company=company)
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, instance=expense, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
            return redirect('erp:expense_list')
    else:
        form = ExpenseForm(instance=expense, company=company)
    
    return render(request, 'erp/expenses/form.html', {
        'form': form,
        'expense': expense,
        'title': 'Edit Expense',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def expense_delete(request, pk):
    """Delete an expense."""
    company = get_user_company(request.user)
    expense = get_object_or_404(Expense, pk=pk, company=company)
    
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
        return redirect('erp:expense_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': expense,
        'object_type': 'Expense',
        'cancel_url': reverse('erp:expense_list'),
    })


# -----------------------------------------------------------------------------
# Quote CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def quote_list(request):
    """List all quotes."""
    company = get_user_company(request.user)
    quotes = Quote.objects.filter(company=company).select_related('customer', 'lead')
    
    # Filters
    status = request.GET.get('status')
    if status:
        quotes = quotes.filter(status=status)
    
    return render(request, 'erp/quotes/list.html', {
        'quotes': quotes.order_by('-quote_date')[:100],
        'statuses': Quote.Status.choices,
    })


@staff_member_required
def quote_detail(request, pk):
    """Quote detail view."""
    company = get_user_company(request.user)
    quote = get_object_or_404(Quote, pk=pk, company=company)
    
    return render(request, 'erp/quotes/detail.html', {
        'quote': quote,
        'lines': quote.lines.all(),
    })


@staff_member_required
def quote_create(request):
    """Create a new quote."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = QuoteForm(request.POST, company=company)
        formset = QuoteLineFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            quote = form.save(commit=False)
            quote.company = company
            quote.save()
            
            formset.instance = quote
            formset.save()
            
            # Recalculate totals
            quote.calculate_totals()
            
            messages.success(request, f'Quote {quote.quote_number} created successfully.')
            return redirect('erp:quote_detail', pk=quote.pk)
    else:
        form = QuoteForm(company=company)
        formset = QuoteLineFormSet()
    
    return render(request, 'erp/quotes/form.html', {
        'form': form,
        'formset': formset,
        'title': 'Create Quote',
        'submit_text': 'Create Quote',
    })


@staff_member_required
def quote_edit(request, pk):
    """Edit an existing quote."""
    company = get_user_company(request.user)
    quote = get_object_or_404(Quote, pk=pk, company=company)
    
    if request.method == 'POST':
        form = QuoteForm(request.POST, instance=quote, company=company)
        formset = QuoteLineFormSet(request.POST, instance=quote)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Recalculate totals
            quote.calculate_totals()
            
            messages.success(request, f'Quote {quote.quote_number} updated successfully.')
            return redirect('erp:quote_detail', pk=quote.pk)
    else:
        form = QuoteForm(instance=quote, company=company)
        formset = QuoteLineFormSet(instance=quote)
    
    return render(request, 'erp/quotes/form.html', {
        'form': form,
        'formset': formset,
        'quote': quote,
        'title': f'Edit Quote: {quote.quote_number}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def quote_delete(request, pk):
    """Delete a quote."""
    company = get_user_company(request.user)
    quote = get_object_or_404(Quote, pk=pk, company=company)
    
    if request.method == 'POST':
        number = quote.quote_number
        quote.delete()
        messages.success(request, f'Quote {number} deleted successfully.')
        return redirect('erp:quote_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': quote,
        'object_type': 'Quote',
        'cancel_url': reverse('erp:quote_detail', args=[pk]),
    })


# -----------------------------------------------------------------------------
# Payment CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def payment_list(request):
    """List all payments."""
    company = get_user_company(request.user)
    payments = Payment.objects.filter(company=company).select_related('customer', 'payment_method', 'currency')
    
    # Filters
    payment_type = request.GET.get('type')
    if payment_type:
        payments = payments.filter(payment_type=payment_type)
    
    return render(request, 'erp/payments/list.html', {
        'payments': payments.order_by('-payment_date')[:100],
        'payment_types': Payment.PaymentType.choices,
    })


@staff_member_required
def payment_create(request):
    """Create a new payment."""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, company=company)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.company = company
            payment.save()
            messages.success(request, f'Payment {payment.payment_number} recorded successfully.')
            return redirect('erp:payment_list')
    else:
        form = PaymentForm(company=company)
        # Pre-fill customer if provided
        customer_id = request.GET.get('customer')
        if customer_id:
            form.fields['customer'].initial = customer_id
    
    return render(request, 'erp/payments/form.html', {
        'form': form,
        'title': 'Record Payment',
        'submit_text': 'Record Payment',
    })


@staff_member_required
def payment_detail(request, pk):
    """Payment detail view."""
    company = get_user_company(request.user)
    payment = get_object_or_404(Payment, pk=pk, company=company)
    
    return render(request, 'erp/payments/detail.html', {
        'payment': payment,
        'allocations': payment.allocations.select_related('invoice'),
    })


@staff_member_required
def payment_delete(request, pk):
    """Delete a payment."""
    company = get_user_company(request.user)
    payment = get_object_or_404(Payment, pk=pk, company=company)
    
    if request.method == 'POST':
        number = payment.payment_number
        payment.delete()
        messages.success(request, f'Payment {number} deleted successfully.')
        return redirect('erp:payment_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': payment,
        'object_type': 'Payment',
        'cancel_url': reverse('erp:payment_detail', args=[pk]),
    })


# -----------------------------------------------------------------------------
# Purchase Order CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def purchase_order_list(request):
    """List all purchase orders."""
    company = get_user_company(request.user)
    orders = PurchaseOrder.objects.filter(company=company).select_related('supplier', 'currency')
    
    # Filters
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
    
    return render(request, 'erp/purchase_orders/list.html', {
        'orders': orders.order_by('-po_date')[:100],
        'statuses': PurchaseOrder.Status.choices,
    })


@staff_member_required
def purchase_order_detail(request, pk):
    """Purchase order detail view."""
    company = get_user_company(request.user)
    order = get_object_or_404(PurchaseOrder, pk=pk, company=company)
    
    return render(request, 'erp/purchase_orders/detail.html', {
        'order': order,
        'lines': order.lines.all(),
    })


@staff_member_required
def purchase_order_create(request):
    """Create a new purchase order."""
    from .forms import PurchaseOrderForm, PurchaseOrderLineFormSet
    
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, company=company)
        formset = PurchaseOrderLineFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            order.company = company
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
        
        # Pre-fill supplier if provided
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
    """Edit an existing purchase order."""
    from .forms import PurchaseOrderForm, PurchaseOrderLineFormSet
    
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
    """Delete a purchase order."""
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


# -----------------------------------------------------------------------------
# Campaign CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def campaign_list(request):
    """List all campaigns."""
    company = get_user_company(request.user)
    campaigns = Campaign.objects.filter(company=company).select_related('owner', 'currency')
    
    # Filters
    status = request.GET.get('status')
    if status:
        campaigns = campaigns.filter(status=status)
    
    return render(request, 'erp/campaigns/list.html', {
        'campaigns': campaigns.order_by('-start_date')[:100],
        'statuses': Campaign.Status.choices,
    })


@staff_member_required
def campaign_detail(request, pk):
    """Campaign detail view."""
    company = get_user_company(request.user)
    campaign = get_object_or_404(Campaign, pk=pk, company=company)
    
    return render(request, 'erp/campaigns/detail.html', {
        'campaign': campaign,
        'leads': campaign.campaign_leads.select_related('lead')[:20],
    })


@staff_member_required
def campaign_create(request):
    """Create a new campaign."""
    from .forms import CampaignForm
    
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, company=company)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.company = company
            campaign.save()
            messages.success(request, f'Campaign "{campaign.name}" created successfully.')
            return redirect('erp:campaign_detail', pk=campaign.pk)
    else:
        form = CampaignForm(company=company)
    
    return render(request, 'erp/campaigns/form.html', {
        'form': form,
        'title': 'Create Campaign',
        'submit_text': 'Create Campaign',
    })


@staff_member_required
def campaign_edit(request, pk):
    """Edit an existing campaign."""
    from .forms import CampaignForm
    
    company = get_user_company(request.user)
    campaign = get_object_or_404(Campaign, pk=pk, company=company)
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Campaign "{campaign.name}" updated successfully.')
            return redirect('erp:campaign_detail', pk=campaign.pk)
    else:
        form = CampaignForm(instance=campaign, company=company)
    
    return render(request, 'erp/campaigns/form.html', {
        'form': form,
        'campaign': campaign,
        'title': f'Edit Campaign: {campaign.name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def campaign_delete(request, pk):
    """Delete a campaign."""
    company = get_user_company(request.user)
    campaign = get_object_or_404(Campaign, pk=pk, company=company)
    
    if request.method == 'POST':
        name = campaign.name
        campaign.delete()
        messages.success(request, f'Campaign "{name}" deleted successfully.')
        return redirect('erp:campaign_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': campaign,
        'object_type': 'Campaign',
        'cancel_url': reverse('erp:campaign_detail', args=[pk]),
    })


# -----------------------------------------------------------------------------
# Department CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def department_list(request):
    """List all departments."""
    company = get_user_company(request.user)
    departments = Department.objects.filter(company=company).select_related('parent', 'manager')
    
    return render(request, 'erp/departments/list.html', {
        'departments': departments.order_by('name'),
    })


@staff_member_required
def department_create(request):
    """Create a new department."""
    from .forms import DepartmentForm
    
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, company=company)
        if form.is_valid():
            department = form.save(commit=False)
            department.company = company
            department.save()
            messages.success(request, f'Department "{department.name}" created successfully.')
            return redirect('erp:department_list')
    else:
        form = DepartmentForm(company=company)
    
    return render(request, 'erp/departments/form.html', {
        'form': form,
        'title': 'Create Department',
        'submit_text': 'Create Department',
    })


@staff_member_required
def department_edit(request, pk):
    """Edit an existing department."""
    from .forms import DepartmentForm
    
    company = get_user_company(request.user)
    department = get_object_or_404(Department, pk=pk, company=company)
    
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Department "{department.name}" updated successfully.')
            return redirect('erp:department_list')
    else:
        form = DepartmentForm(instance=department, company=company)
    
    return render(request, 'erp/departments/form.html', {
        'form': form,
        'department': department,
        'title': f'Edit Department: {department.name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def department_delete(request, pk):
    """Delete a department."""
    company = get_user_company(request.user)
    department = get_object_or_404(Department, pk=pk, company=company)
    
    if request.method == 'POST':
        name = department.name
        department.delete()
        messages.success(request, f'Department "{name}" deleted successfully.')
        return redirect('erp:department_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': department,
        'object_type': 'Department',
        'cancel_url': reverse('erp:department_list'),
    })


# -----------------------------------------------------------------------------
# Attendance Management
# -----------------------------------------------------------------------------

@staff_member_required
def attendance_list(request):
    """List attendance records."""
    company = get_user_company(request.user)
    from datetime import date, timedelta
    
    # Default to current month
    today = date.today()
    start_date = request.GET.get('start_date', today.replace(day=1).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())
    
    attendances = Attendance.objects.filter(
        employee__company=company,
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee').order_by('-date', 'employee__first_name')
    
    return render(request, 'erp/attendance/list.html', {
        'attendances': attendances[:200],
        'start_date': start_date,
        'end_date': end_date,
    })


@staff_member_required
def attendance_create(request):
    """Record attendance."""
    from .forms import AttendanceForm
    
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = AttendanceForm(request.POST, company=company)
        if form.is_valid():
            attendance = form.save()
            messages.success(request, f'Attendance recorded for {attendance.employee.full_name}.')
            return redirect('erp:attendance_list')
    else:
        form = AttendanceForm(company=company)
    
    return render(request, 'erp/attendance/form.html', {
        'form': form,
        'title': 'Record Attendance',
        'submit_text': 'Save Attendance',
    })


@staff_member_required
def attendance_edit(request, pk):
    """Edit attendance record."""
    from .forms import AttendanceForm
    
    company = get_user_company(request.user)
    attendance = get_object_or_404(Attendance, pk=pk, employee__company=company)
    
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attendance updated successfully.')
            return redirect('erp:attendance_list')
    else:
        form = AttendanceForm(instance=attendance, company=company)
    
    return render(request, 'erp/attendance/form.html', {
        'form': form,
        'attendance': attendance,
        'title': f'Edit Attendance: {attendance.employee.full_name} - {attendance.date}',
        'submit_text': 'Save Changes',
    })


# -----------------------------------------------------------------------------
# Leave Request Management
# -----------------------------------------------------------------------------

@staff_member_required
def leave_request_list(request):
    """List all leave requests."""
    company = get_user_company(request.user)
    leave_requests = LeaveRequest.objects.filter(
        employee__company=company
    ).select_related('employee', 'leave_type', 'approved_by').order_by('-created_at')
    
    # Filters
    status = request.GET.get('status')
    if status:
        leave_requests = leave_requests.filter(status=status)
    
    return render(request, 'erp/leave_requests/list.html', {
        'leave_requests': leave_requests[:100],
        'statuses': LeaveRequest.Status.choices,
    })


@staff_member_required
def leave_request_create(request):
    """Create a new leave request."""
    from .forms import LeaveRequestForm
    
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, company=company)
        if form.is_valid():
            leave_request = form.save()
            messages.success(request, 'Leave request submitted successfully.')
            return redirect('erp:leave_request_list')
    else:
        form = LeaveRequestForm(company=company)
    
    return render(request, 'erp/leave_requests/form.html', {
        'form': form,
        'title': 'Submit Leave Request',
        'submit_text': 'Submit Request',
    })


@staff_member_required
def leave_request_detail(request, pk):
    """Leave request detail view."""
    company = get_user_company(request.user)
    leave_request = get_object_or_404(LeaveRequest, pk=pk, employee__company=company)
    
    return render(request, 'erp/leave_requests/detail.html', {
        'leave_request': leave_request,
    })


@staff_member_required
def leave_request_approve(request, pk):
    """Approve or reject a leave request."""
    company = get_user_company(request.user)
    leave_request = get_object_or_404(LeaveRequest, pk=pk, employee__company=company)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        # Get approving employee
        try:
            approver = request.user.employee_profile
        except:
            approver = None
        
        if action == 'approve':
            leave_request.status = 'approved'
            leave_request.approved_by = approver
            leave_request.approval_date = timezone.now()
            leave_request.approval_notes = notes
            leave_request.save()
            messages.success(request, 'Leave request approved.')
        elif action == 'reject':
            leave_request.status = 'rejected'
            leave_request.approved_by = approver
            leave_request.approval_date = timezone.now()
            leave_request.approval_notes = notes
            leave_request.save()
            messages.warning(request, 'Leave request rejected.')
        
        return redirect('erp:leave_request_detail', pk=pk)
    
    return redirect('erp:leave_request_detail', pk=pk)


# =============================================================================
# FINANCIAL MODULE VIEWS
# =============================================================================

# -----------------------------------------------------------------------------
# Account (Chart of Accounts) CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def account_list(request):
    """List all accounts (Chart of Accounts)."""
    company = get_user_company(request.user)
    from .models import Account
    
    accounts = Account.objects.filter(company=company) if company else Account.objects.none()
    
    # Filter by account type
    account_type = request.GET.get('type')
    if account_type:
        accounts = accounts.filter(account_type=account_type)
    
    # Group by account type for display
    account_types = {}
    for acc in accounts:
        if acc.account_type not in account_types:
            account_types[acc.account_type] = []
        account_types[acc.account_type].append(acc)
    
    return render(request, 'erp/accounts/list.html', {
        'accounts': accounts,
        'account_types': account_types,
        'company': company,
    })


@staff_member_required
def account_create(request):
    """Create a new account."""
    company = get_user_company(request.user)
    from .forms import AccountForm
    
    if request.method == 'POST':
        form = AccountForm(request.POST, company=company)
        if form.is_valid():
            account = form.save(commit=False)
            account.company = company
            account.save()
            messages.success(request, f'Account "{account.code} - {account.name}" created successfully.')
            return redirect('erp:account_list')
    else:
        form = AccountForm(company=company)
    
    return render(request, 'erp/accounts/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def account_edit(request, pk):
    """Edit an existing account."""
    company = get_user_company(request.user)
    from .models import Account
    from .forms import AccountForm
    
    account = get_object_or_404(Account, pk=pk, company=company)
    
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Account "{account.code} - {account.name}" updated successfully.')
            return redirect('erp:account_list')
    else:
        form = AccountForm(instance=account, company=company)
    
    return render(request, 'erp/accounts/form.html', {
        'form': form,
        'account': account,
        'company': company,
    })


@staff_member_required
def account_delete(request, pk):
    """Delete an account."""
    company = get_user_company(request.user)
    from .models import Account
    
    account = get_object_or_404(Account, pk=pk, company=company)
    
    if request.method == 'POST':
        if account.is_system:
            messages.error(request, 'System accounts cannot be deleted.')
        else:
            account.delete()
            messages.success(request, 'Account deleted successfully.')
        return redirect('erp:account_list')
    
    return redirect('erp:account_list')


# -----------------------------------------------------------------------------
# Tax Rate CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def tax_rate_list(request):
    """List all tax rates."""
    company = get_user_company(request.user)
    from .models import TaxRate
    
    tax_rates = TaxRate.objects.filter(company=company) if company else TaxRate.objects.none()
    
    return render(request, 'erp/tax_rates/list.html', {
        'tax_rates': tax_rates,
        'company': company,
    })


@staff_member_required
def tax_rate_create(request):
    """Create a new tax rate."""
    company = get_user_company(request.user)
    from .forms import TaxRateForm
    
    if request.method == 'POST':
        form = TaxRateForm(request.POST, company=company)
        if form.is_valid():
            tax_rate = form.save(commit=False)
            tax_rate.company = company
            tax_rate.save()
            messages.success(request, f'Tax rate "{tax_rate.name}" created successfully.')
            return redirect('erp:tax_rate_list')
    else:
        form = TaxRateForm(company=company)
    
    return render(request, 'erp/tax_rates/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def tax_rate_edit(request, pk):
    """Edit an existing tax rate."""
    company = get_user_company(request.user)
    from .models import TaxRate
    from .forms import TaxRateForm
    
    tax_rate = get_object_or_404(TaxRate, pk=pk, company=company)
    
    if request.method == 'POST':
        form = TaxRateForm(request.POST, instance=tax_rate, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tax rate "{tax_rate.name}" updated successfully.')
            return redirect('erp:tax_rate_list')
    else:
        form = TaxRateForm(instance=tax_rate, company=company)
    
    return render(request, 'erp/tax_rates/form.html', {
        'form': form,
        'tax_rate': tax_rate,
        'company': company,
    })


@staff_member_required
def tax_rate_delete(request, pk):
    """Delete a tax rate."""
    company = get_user_company(request.user)
    from .models import TaxRate
    
    tax_rate = get_object_or_404(TaxRate, pk=pk, company=company)
    
    if request.method == 'POST':
        tax_rate.delete()
        messages.success(request, 'Tax rate deleted successfully.')
        return redirect('erp:tax_rate_list')
    
    return redirect('erp:tax_rate_list')


# -----------------------------------------------------------------------------
# Payment Method CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def payment_method_list(request):
    """List all payment methods."""
    company = get_user_company(request.user)
    from .models import PaymentMethod
    
    payment_methods = PaymentMethod.objects.filter(company=company) if company else PaymentMethod.objects.none()
    
    return render(request, 'erp/payment_methods/list.html', {
        'payment_methods': payment_methods,
        'company': company,
    })


@staff_member_required
def payment_method_create(request):
    """Create a new payment method."""
    company = get_user_company(request.user)
    from .forms import PaymentMethodForm
    
    if request.method == 'POST':
        form = PaymentMethodForm(request.POST, company=company)
        if form.is_valid():
            payment_method = form.save(commit=False)
            payment_method.company = company
            payment_method.save()
            messages.success(request, f'Payment method "{payment_method.name}" created successfully.')
            return redirect('erp:payment_method_list')
    else:
        form = PaymentMethodForm(company=company)
    
    return render(request, 'erp/payment_methods/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def payment_method_edit(request, pk):
    """Edit an existing payment method."""
    company = get_user_company(request.user)
    from .models import PaymentMethod
    from .forms import PaymentMethodForm
    
    payment_method = get_object_or_404(PaymentMethod, pk=pk, company=company)
    
    if request.method == 'POST':
        form = PaymentMethodForm(request.POST, instance=payment_method, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Payment method "{payment_method.name}" updated successfully.')
            return redirect('erp:payment_method_list')
    else:
        form = PaymentMethodForm(instance=payment_method, company=company)
    
    return render(request, 'erp/payment_methods/form.html', {
        'form': form,
        'payment_method': payment_method,
        'company': company,
    })


@staff_member_required
def payment_method_delete(request, pk):
    """Delete a payment method."""
    company = get_user_company(request.user)
    from .models import PaymentMethod
    
    payment_method = get_object_or_404(PaymentMethod, pk=pk, company=company)
    
    if request.method == 'POST':
        payment_method.delete()
        messages.success(request, 'Payment method deleted successfully.')
        return redirect('erp:payment_method_list')
    
    return redirect('erp:payment_method_list')


# -----------------------------------------------------------------------------
# Expense Category CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def expense_category_list(request):
    """List all expense categories."""
    company = get_user_company(request.user)
    from .models import ExpenseCategory
    
    expense_categories = ExpenseCategory.objects.filter(company=company) if company else ExpenseCategory.objects.none()
    
    return render(request, 'erp/expense_categories/list.html', {
        'expense_categories': expense_categories,
        'company': company,
    })


@staff_member_required
def expense_category_create(request):
    """Create a new expense category."""
    company = get_user_company(request.user)
    from .forms import ExpenseCategoryForm
    
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, company=company)
        if form.is_valid():
            expense_category = form.save(commit=False)
            expense_category.company = company
            expense_category.save()
            messages.success(request, f'Expense category "{expense_category.name}" created successfully.')
            return redirect('erp:expense_category_list')
    else:
        form = ExpenseCategoryForm(company=company)
    
    return render(request, 'erp/expense_categories/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def expense_category_edit(request, pk):
    """Edit an existing expense category."""
    company = get_user_company(request.user)
    from .models import ExpenseCategory
    from .forms import ExpenseCategoryForm
    
    expense_category = get_object_or_404(ExpenseCategory, pk=pk, company=company)
    
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=expense_category, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Expense category "{expense_category.name}" updated successfully.')
            return redirect('erp:expense_category_list')
    else:
        form = ExpenseCategoryForm(instance=expense_category, company=company)
    
    return render(request, 'erp/expense_categories/form.html', {
        'form': form,
        'expense_category': expense_category,
        'company': company,
    })


@staff_member_required
def expense_category_delete(request, pk):
    """Delete an expense category."""
    company = get_user_company(request.user)
    from .models import ExpenseCategory
    
    expense_category = get_object_or_404(ExpenseCategory, pk=pk, company=company)
    
    if request.method == 'POST':
        expense_category.delete()
        messages.success(request, 'Expense category deleted successfully.')
        return redirect('erp:expense_category_list')
    
    return redirect('erp:expense_category_list')


# -----------------------------------------------------------------------------
# Currency CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def currency_list(request):
    """List all currencies."""
    company = get_user_company(request.user)
    from .models import Currency
    
    currencies = Currency.objects.all()
    
    return render(request, 'erp/currencies/list.html', {
        'currencies': currencies,
        'company': company,
    })


@staff_member_required
def currency_create(request):
    """Create a new currency."""
    company = get_user_company(request.user)
    from .forms import CurrencyForm
    
    if request.method == 'POST':
        form = CurrencyForm(request.POST)
        if form.is_valid():
            currency = form.save()
            messages.success(request, f'Currency "{currency.code}" created successfully.')
            return redirect('erp:currency_list')
    else:
        form = CurrencyForm()
    
    return render(request, 'erp/currencies/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def currency_edit(request, pk):
    """Edit an existing currency."""
    company = get_user_company(request.user)
    from .models import Currency
    from .forms import CurrencyForm
    
    currency = get_object_or_404(Currency, pk=pk)
    
    if request.method == 'POST':
        form = CurrencyForm(request.POST, instance=currency)
        if form.is_valid():
            form.save()
            messages.success(request, f'Currency "{currency.code}" updated successfully.')
            return redirect('erp:currency_list')
    else:
        form = CurrencyForm(instance=currency)
    
    return render(request, 'erp/currencies/form.html', {
        'form': form,
        'currency': currency,
        'company': company,
    })


@staff_member_required
def currency_delete(request, pk):
    """Delete a currency."""
    from .models import Currency
    
    currency = get_object_or_404(Currency, pk=pk)
    
    if request.method == 'POST':
        currency.delete()
        messages.success(request, 'Currency deleted successfully.')
        return redirect('erp:currency_list')
    
    return redirect('erp:currency_list')


# -----------------------------------------------------------------------------
# Fiscal Year CRUD
# -----------------------------------------------------------------------------

@staff_member_required
def fiscal_year_list(request):
    """List all fiscal years."""
    company = get_user_company(request.user)
    from .models import FiscalYear
    
    fiscal_years = FiscalYear.objects.filter(company=company) if company else FiscalYear.objects.none()
    
    return render(request, 'erp/fiscal_years/list.html', {
        'fiscal_years': fiscal_years,
        'company': company,
    })


@staff_member_required
def fiscal_year_create(request):
    """Create a new fiscal year."""
    company = get_user_company(request.user)
    from .forms import FiscalYearForm
    
    if request.method == 'POST':
        form = FiscalYearForm(request.POST, company=company)
        if form.is_valid():
            fiscal_year = form.save(commit=False)
            fiscal_year.company = company
            fiscal_year.save()
            messages.success(request, f'Fiscal year "{fiscal_year.name}" created successfully.')
            return redirect('erp:fiscal_year_list')
    else:
        form = FiscalYearForm(company=company)
    
    return render(request, 'erp/fiscal_years/form.html', {
        'form': form,
        'company': company,
    })


@staff_member_required
def fiscal_year_edit(request, pk):
    """Edit an existing fiscal year."""
    company = get_user_company(request.user)
    from .models import FiscalYear
    from .forms import FiscalYearForm
    
    fiscal_year = get_object_or_404(FiscalYear, pk=pk, company=company)
    
    if request.method == 'POST':
        form = FiscalYearForm(request.POST, instance=fiscal_year, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Fiscal year "{fiscal_year.name}" updated successfully.')
            return redirect('erp:fiscal_year_list')
    else:
        form = FiscalYearForm(instance=fiscal_year, company=company)
    
    return render(request, 'erp/fiscal_years/form.html', {
        'form': form,
        'fiscal_year': fiscal_year,
        'company': company,
    })


@staff_member_required
def fiscal_year_delete(request, pk):
    """Delete a fiscal year."""
    company = get_user_company(request.user)
    from .models import FiscalYear
    
    fiscal_year = get_object_or_404(FiscalYear, pk=pk, company=company)
    
    if request.method == 'POST':
        fiscal_year.delete()
        messages.success(request, 'Fiscal year deleted successfully.')
        return redirect('erp:fiscal_year_list')
    
    return redirect('erp:fiscal_year_list')


# -----------------------------------------------------------------------------
# Financial Reports
# -----------------------------------------------------------------------------

@staff_member_required
def financial_reports(request):
    """Financial reports overview page."""
    company = get_user_company(request.user)
    from .models import Account, Invoice, Expense, Payment
    
    # Get date range
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)
    
    context = {
        'company': company,
        'today': today,
    }
    
    if company:
        # Revenue (paid invoices)
        context['monthly_revenue'] = Invoice.objects.filter(
            company=company,
            status='paid',
            invoice_date__gte=start_of_month
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        context['yearly_revenue'] = Invoice.objects.filter(
            company=company,
            status='paid',
            invoice_date__gte=start_of_year
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Expenses
        context['monthly_expenses'] = Expense.objects.filter(
            company=company,
            expense_date__gte=start_of_month
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        context['yearly_expenses'] = Expense.objects.filter(
            company=company,
            expense_date__gte=start_of_year
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Profit
        context['monthly_profit'] = context['monthly_revenue'] - context['monthly_expenses']
        context['yearly_profit'] = context['yearly_revenue'] - context['yearly_expenses']
        
        # Receivables (unpaid invoices)
        context['total_receivables'] = Invoice.objects.filter(
            company=company,
            status__in=['sent', 'partial', 'overdue']
        ).aggregate(total=Sum('balance_due'))['total'] or 0
        
        # Recent transactions
        context['recent_invoices'] = Invoice.objects.filter(
            company=company
        ).order_by('-invoice_date')[:5]
        
        context['recent_payments'] = Payment.objects.filter(
            company=company
        ).order_by('-payment_date')[:5]
        
        context['recent_expenses'] = Expense.objects.filter(
            company=company
        ).order_by('-expense_date')[:5]
        
        # Account balances
        context['accounts'] = Account.objects.filter(
            company=company,
            is_active=True
        ).order_by('account_type', 'code')[:10]
    
    return render(request, 'erp/finance/reports.html', context)


# =============================================================================
# JOURNAL ENTRIES - القيود اليومية
# =============================================================================

@staff_member_required
def journal_entry_list(request):
    """قائمة القيود اليومية"""
    company = get_user_company(request.user)
    entries = JournalEntry.objects.filter(company=company).order_by('-entry_date', '-entry_number')
    
    # Filtering
    status = request.GET.get('status')
    entry_type = request.GET.get('type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        entries = entries.filter(status=status)
    if entry_type:
        entries = entries.filter(entry_type=entry_type)
    if date_from:
        entries = entries.filter(entry_date__gte=date_from)
    if date_to:
        entries = entries.filter(entry_date__lte=date_to)
    
    # Stats
    total_entries = entries.count()
    posted_count = entries.filter(status='posted').count()
    draft_count = entries.filter(status='draft').count()
    
    context = {
        'entries': entries[:50],
        'total_entries': total_entries,
        'posted_count': posted_count,
        'draft_count': draft_count,
        'status_choices': JournalEntry.Status.choices,
        'type_choices': JournalEntry.EntryType.choices,
    }
    return render(request, 'erp/journal_entries/list.html', context)


@staff_member_required
def journal_entry_create(request):
    """إنشاء قيد يومية جديد"""
    company = get_user_company(request.user)
    
    if request.method == 'POST':
        form = JournalEntryForm(request.POST, company=company)
        formset = JournalEntryLineFormSet(request.POST, company=company)
        
        if form.is_valid() and formset.is_valid():
            journal_entry = form.save(commit=False)
            journal_entry.company = company
            journal_entry.created_by = request.user
            journal_entry.save()
            
            formset.instance = journal_entry
            formset.save()
            
            # Recalculate totals
            journal_entry.calculate_totals()
            journal_entry.save()
            
            messages.success(request, f'تم إنشاء القيد رقم {journal_entry.entry_number} بنجاح')
            return redirect('erp:journal_entry_detail', pk=journal_entry.pk)
    else:
        # Generate next entry number
        from django.utils import timezone
        today = timezone.now().date()
        last_entry = JournalEntry.objects.filter(company=company).order_by('-id').first()
        next_num = 1 if not last_entry else int(last_entry.entry_number.split('-')[-1]) + 1
        initial_number = f"JE-{today.year}-{next_num:05d}"
        
        form = JournalEntryForm(company=company, initial={
            'entry_number': initial_number,
            'entry_date': today,
        })
        formset = JournalEntryLineFormSet(company=company)
    
    return render(request, 'erp/journal_entries/form.html', {
        'form': form,
        'formset': formset,
        'accounts': Account.objects.filter(company=company, is_active=True).order_by('code'),
    })


@staff_member_required
def journal_entry_detail(request, pk):
    """عرض تفاصيل القيد"""
    company = get_user_company(request.user)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    
    return render(request, 'erp/journal_entries/detail.html', {
        'entry': entry,
        'lines': entry.lines.all().select_related('account'),
    })


@staff_member_required
def journal_entry_edit(request, pk):
    """تعديل قيد يومية"""
    company = get_user_company(request.user)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    
    if entry.status == 'posted':
        messages.error(request, 'لا يمكن تعديل قيد مرحّل')
        return redirect('erp:journal_entry_detail', pk=pk)
    
    if request.method == 'POST':
        form = JournalEntryForm(request.POST, instance=entry, company=company)
        formset = JournalEntryLineFormSet(request.POST, instance=entry, company=company)
        
        if form.is_valid() and formset.is_valid():
            journal_entry = form.save()
            formset.save()
            
            # Recalculate totals
            journal_entry.calculate_totals()
            journal_entry.save()
            
            messages.success(request, 'تم تحديث القيد بنجاح')
            return redirect('erp:journal_entry_detail', pk=pk)
    else:
        form = JournalEntryForm(instance=entry, company=company)
        formset = JournalEntryLineFormSet(instance=entry, company=company)
    
    return render(request, 'erp/journal_entries/form.html', {
        'form': form,
        'formset': formset,
        'entry': entry,
        'accounts': Account.objects.filter(company=company, is_active=True).order_by('code'),
    })


@staff_member_required
def journal_entry_delete(request, pk):
    """حذف قيد يومية"""
    company = get_user_company(request.user)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    
    if entry.status == 'posted':
        messages.error(request, 'لا يمكن حذف قيد مرحّل')
        return redirect('erp:journal_entry_detail', pk=pk)
    
    if request.method == 'POST':
        entry_number = entry.entry_number
        entry.delete()
        messages.success(request, f'تم حذف القيد رقم {entry_number}')
        return redirect('erp:journal_entry_list')
    
    return render(request, 'erp/confirm_delete.html', {
        'object': entry,
        'object_name': f'القيد رقم {entry.entry_number}',
        'cancel_url': reverse('erp:journal_entry_detail', args=[pk]),
    })


@staff_member_required
def journal_entry_post(request, pk):
    """ترحيل القيد"""
    company = get_user_company(request.user)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)
    
    if request.method == 'POST':
        try:
            entry.post(request.user)
            messages.success(request, f'تم ترحيل القيد رقم {entry.entry_number} بنجاح')
        except ValueError as e:
            messages.error(request, str(e))
    
    return redirect('erp:journal_entry_detail', pk=pk)


# =============================================================================
# PRODUCT CATEGORIES
# =============================================================================

@staff_member_required
def product_category_list(request):
    """List product categories."""
    company = get_user_company(request.user)
    categories = ProductCategory.objects.filter(company=company)
    return render(request, 'erp/product_categories/list.html', {
        'categories': categories,
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


# =============================================================================
# PRODUCTS
# =============================================================================

@staff_member_required
def product_list(request):
    """List products with search & filters."""
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

    return render(request, 'erp/products/list.html', {
        'products': products.order_by('name')[:200],
        'categories': ProductCategory.objects.filter(company=company, is_active=True),
        'product_types': Product.ProductType.choices,
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


# =============================================================================
# SERVICE CATEGORIES
# =============================================================================

@staff_member_required
def service_category_list(request):
    company = get_user_company(request.user)
    categories = ServiceCategory.objects.filter(company=company)
    return render(request, 'erp/service_categories/list.html', {
        'categories': categories,
    })


@staff_member_required
def service_category_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.save()
            messages.success(request, f'تمت إضافة تصنيف الخدمة "{obj.name}" بنجاح.')
            return redirect('erp:service_category_list')
    else:
        form = ServiceCategoryForm(company=company)
    return render(request, 'erp/service_categories/form.html', {
        'form': form, 'title': 'إضافة تصنيف خدمة', 'submit_text': 'حفظ',
    })


@staff_member_required
def service_category_edit(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(ServiceCategory, pk=pk, company=company)
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST, instance=obj, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث تصنيف الخدمة بنجاح.')
            return redirect('erp:service_category_list')
    else:
        form = ServiceCategoryForm(instance=obj, company=company)
    return render(request, 'erp/service_categories/form.html', {
        'form': form, 'title': 'تعديل تصنيف خدمة', 'submit_text': 'حفظ التغييرات',
    })


@staff_member_required
def service_category_delete(request, pk):
    company = get_user_company(request.user)
    obj = get_object_or_404(ServiceCategory, pk=pk, company=company)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'تم حذف تصنيف الخدمة بنجاح.')
        return redirect('erp:service_category_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': obj, 'object_type': 'تصنيف خدمة',
        'cancel_url': reverse('erp:service_category_list'),
    })


# =============================================================================
# SERVICES (ServicePricing)
# =============================================================================

@staff_member_required
def service_list(request):
    company = get_user_company(request.user)
    services = ServicePricing.objects.filter(company=company).select_related('category', 'currency', 'tax_rate')

    search = request.GET.get('search', '').strip()
    if search:
        services = services.filter(
            Q(name__icontains=search) | Q(code__icontains=search) | Q(name_ar__icontains=search)
        )
    cat = request.GET.get('category')
    if cat:
        services = services.filter(category_id=cat)

    return render(request, 'erp/services/list.html', {
        'services': services.order_by('name')[:200],
        'categories': ServiceCategory.objects.filter(company=company, is_active=True),
    })


@staff_member_required
def service_detail(request, pk):
    company = get_user_company(request.user)
    service = get_object_or_404(ServicePricing, pk=pk, company=company)
    price_tiers = service.price_tiers.all().order_by('min_quantity')
    quote_lines = service.quote_lines.select_related('quote__customer').order_by('-quote__quote_date')[:20]
    invoice_lines = service.invoice_lines.select_related('invoice__customer').order_by('-invoice__invoice_date')[:20]
    return render(request, 'erp/services/detail.html', {
        'service': service,
        'price_tiers': price_tiers,
        'quote_lines': quote_lines,
        'invoice_lines': invoice_lines,
    })


@staff_member_required
def service_create(request):
    company = get_user_company(request.user)
    if request.method == 'POST':
        form = ServicePricingForm(request.POST, company=company)
        if form.is_valid():
            service = form.save(commit=False)
            service.company = company
            service.save()
            messages.success(request, f'تمت إضافة الخدمة "{service.name}" بنجاح.')
            return redirect('erp:service_detail', pk=service.pk)
    else:
        form = ServicePricingForm(company=company)
    return render(request, 'erp/services/form.html', {
        'form': form, 'title': 'إضافة خدمة', 'submit_text': 'حفظ الخدمة',
    })


@staff_member_required
def service_edit(request, pk):
    company = get_user_company(request.user)
    service = get_object_or_404(ServicePricing, pk=pk, company=company)
    if request.method == 'POST':
        form = ServicePricingForm(request.POST, instance=service, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الخدمة بنجاح.')
            return redirect('erp:service_detail', pk=service.pk)
    else:
        form = ServicePricingForm(instance=service, company=company)
    return render(request, 'erp/services/form.html', {
        'form': form, 'title': 'تعديل خدمة', 'submit_text': 'حفظ التغييرات',
    })


@staff_member_required
def service_delete(request, pk):
    company = get_user_company(request.user)
    service = get_object_or_404(ServicePricing, pk=pk, company=company)
    if request.method == 'POST':
        service.delete()
        messages.success(request, 'تم حذف الخدمة بنجاح.')
        return redirect('erp:service_list')
    return render(request, 'erp/confirm_delete.html', {
        'object': service, 'object_type': 'خدمة',
        'cancel_url': reverse('erp:service_detail', args=[pk]),
    })
