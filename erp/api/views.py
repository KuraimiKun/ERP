"""
ERP API ViewSets

Django REST Framework ViewSets for the ERP system.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone

from ..models import (
    # Core
    Currency, Company, Department, Branch, FiscalYear,
    # HR
    Employee, LeaveType, LeaveRequest, Attendance, Payroll,
    # Finance
    Account, TaxRate, PaymentMethod, Customer, Invoice, InvoiceLine,
    Payment, Expense, ExpenseCategory,
    # Supplier
    Supplier, SupplierContact, PurchaseOrder,
    # CRM
    Lead, LeadActivity, CustomerInteraction, Campaign, Task, TaskComment,
    # Services
    ServiceCategory, ServicePricing, Quote,
    # Reporting
    Dashboard, DashboardWidget, KPI, KPIValue,
    # Audit
    AuditLog, Notification,
)

from .serializers import (
    # Core
    CurrencySerializer, CompanySerializer, DepartmentSerializer,
    BranchSerializer, FiscalYearSerializer,
    # HR
    EmployeeSerializer, EmployeeListSerializer, LeaveTypeSerializer,
    LeaveRequestSerializer, AttendanceSerializer, PayrollSerializer,
    # Finance
    AccountSerializer, TaxRateSerializer, PaymentMethodSerializer,
    CustomerSerializer, CustomerListSerializer, InvoiceSerializer,
    InvoiceListSerializer, InvoiceLineSerializer, PaymentSerializer,
    ExpenseSerializer, ExpenseCategorySerializer,
    # Supplier
    SupplierSerializer, SupplierListSerializer, SupplierContactSerializer,
    PurchaseOrderSerializer,
    # CRM
    LeadSerializer, LeadListSerializer, LeadActivitySerializer,
    CustomerInteractionSerializer, CampaignSerializer,
    TaskSerializer, TaskListSerializer, TaskCommentSerializer,
    # Services
    ServiceCategorySerializer, ServicePricingSerializer,
    QuoteSerializer, QuoteListSerializer,
    # Reporting
    DashboardSerializer, DashboardWidgetSerializer, KPISerializer,
    # Audit
    AuditLogSerializer, NotificationSerializer,
)


class ERPBaseViewSet(viewsets.ModelViewSet):
    """Base ViewSet with common functionality for ERP views."""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    def get_company(self):
        """Get the current user's company."""
        user = self.request.user
        if hasattr(user, 'employee_profile') and user.employee_profile:
            return user.employee_profile.company
        return Company.objects.first()
    
    def get_queryset(self):
        """Filter queryset by company."""
        queryset = super().get_queryset()
        company = self.get_company()
        if company and hasattr(queryset.model, 'company'):
            return queryset.filter(company=company)
        return queryset


# =============================================================================
# Core ViewSets
# =============================================================================

class CurrencyViewSet(viewsets.ModelViewSet):
    """API endpoint for currencies."""
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['code', 'name']


class CompanyViewSet(viewsets.ModelViewSet):
    """API endpoint for companies."""
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'legal_name']


class DepartmentViewSet(ERPBaseViewSet):
    """API endpoint for departments."""
    queryset = Department.objects.select_related('parent', 'manager')
    serializer_class = DepartmentSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['is_active', 'parent']


class BranchViewSet(ERPBaseViewSet):
    """API endpoint for branches."""
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    search_fields = ['name', 'code', 'city']
    filterset_fields = ['is_active', 'is_headquarters']


class FiscalYearViewSet(ERPBaseViewSet):
    """API endpoint for fiscal years."""
    queryset = FiscalYear.objects.all()
    serializer_class = FiscalYearSerializer
    filterset_fields = ['is_current', 'is_closed']


# =============================================================================
# HR ViewSets
# =============================================================================

class EmployeeViewSet(ERPBaseViewSet):
    """API endpoint for employees."""
    queryset = Employee.objects.select_related('department', 'branch', 'reports_to')
    serializer_class = EmployeeSerializer
    search_fields = ['first_name', 'last_name', 'email', 'employee_id']
    filterset_fields = ['department', 'branch', 'employment_status', 'employment_type', 'is_active']
    ordering_fields = ['first_name', 'last_name', 'hire_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EmployeeListSerializer
        return EmployeeSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get the current user's employee profile."""
        if hasattr(request.user, 'employee_profile') and request.user.employee_profile:
            serializer = self.get_serializer(request.user.employee_profile)
            return Response(serializer.data)
        return Response({'detail': 'No employee profile found.'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        """Get attendance records for an employee."""
        employee = self.get_object()
        attendances = employee.attendances.order_by('-date')[:30]
        serializer = AttendanceSerializer(attendances, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def leave_requests(self, request, pk=None):
        """Get leave requests for an employee."""
        employee = self.get_object()
        leaves = employee.leave_requests.order_by('-created_at')
        serializer = LeaveRequestSerializer(leaves, many=True)
        return Response(serializer.data)


class LeaveTypeViewSet(ERPBaseViewSet):
    """API endpoint for leave types."""
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    filterset_fields = ['is_active', 'is_paid', 'requires_approval']


class LeaveRequestViewSet(ERPBaseViewSet):
    """API endpoint for leave requests."""
    queryset = LeaveRequest.objects.select_related('employee', 'leave_type', 'approved_by')
    serializer_class = LeaveRequestSerializer
    filterset_fields = ['employee', 'leave_type', 'status']
    ordering_fields = ['start_date', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        company = self.get_company()
        if company:
            return queryset.filter(employee__company=company)
        return queryset
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a leave request."""
        leave_request = self.get_object()
        if leave_request.status != 'pending':
            return Response({'detail': 'Can only approve pending requests.'}, status=status.HTTP_400_BAD_REQUEST)
        
        leave_request.status = 'approved'
        if hasattr(request.user, 'employee_profile'):
            leave_request.approved_by = request.user.employee_profile
        leave_request.approved_at = timezone.now()
        leave_request.save()
        
        serializer = self.get_serializer(leave_request)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a leave request."""
        leave_request = self.get_object()
        if leave_request.status != 'pending':
            return Response({'detail': 'Can only reject pending requests.'}, status=status.HTTP_400_BAD_REQUEST)
        
        leave_request.status = 'rejected'
        leave_request.rejection_reason = request.data.get('reason', '')
        leave_request.save()
        
        serializer = self.get_serializer(leave_request)
        return Response(serializer.data)


class AttendanceViewSet(ERPBaseViewSet):
    """API endpoint for attendance records."""
    queryset = Attendance.objects.select_related('employee')
    serializer_class = AttendanceSerializer
    filterset_fields = ['employee', 'status', 'date']
    ordering_fields = ['date', 'check_in']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        company = self.get_company()
        if company:
            return queryset.filter(employee__company=company)
        return queryset


class PayrollViewSet(ERPBaseViewSet):
    """API endpoint for payroll records."""
    queryset = Payroll.objects.select_related('employee')
    serializer_class = PayrollSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['employee', 'status']
    ordering_fields = ['period_start', 'payment_date']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        company = self.get_company()
        if company:
            return queryset.filter(employee__company=company)
        return queryset


# =============================================================================
# Finance ViewSets
# =============================================================================

class AccountViewSet(ERPBaseViewSet):
    """API endpoint for chart of accounts."""
    queryset = Account.objects.select_related('parent')
    serializer_class = AccountSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['account_type', 'is_active', 'parent']


class TaxRateViewSet(ERPBaseViewSet):
    """API endpoint for tax rates."""
    queryset = TaxRate.objects.all()
    serializer_class = TaxRateSerializer
    filterset_fields = ['is_active']


class PaymentMethodViewSet(ERPBaseViewSet):
    """API endpoint for payment methods."""
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    filterset_fields = ['is_active']


class CustomerViewSet(ERPBaseViewSet):
    """API endpoint for customers."""
    queryset = Customer.objects.select_related('currency')
    serializer_class = CustomerSerializer
    search_fields = ['name', 'email', 'customer_id', 'phone']
    filterset_fields = ['customer_type', 'is_active']
    ordering_fields = ['name', 'created_at', 'balance']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerListSerializer
        return CustomerSerializer
    
    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        """Get invoices for a customer."""
        customer = self.get_object()
        invoices = customer.invoices.order_by('-invoice_date')
        serializer = InvoiceListSerializer(invoices, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statement(self, request, pk=None):
        """Get account statement for a customer."""
        customer = self.get_object()
        invoices = customer.invoices.values('invoice_number', 'invoice_date', 'total_amount', 'balance_due', 'status')
        payments = customer.payments.values('payment_number', 'payment_date', 'amount')
        
        return Response({
            'customer': CustomerListSerializer(customer).data,
            'balance': customer.balance,
            'invoices': list(invoices),
            'payments': list(payments),
        })
    
    @action(detail=True, methods=['get'])
    def interactions(self, request, pk=None):
        """Get interaction history for a customer."""
        customer = self.get_object()
        interactions = customer.interactions.order_by('-interaction_date')
        serializer = CustomerInteractionSerializer(interactions, many=True)
        return Response(serializer.data)


class InvoiceViewSet(ERPBaseViewSet):
    """API endpoint for invoices."""
    queryset = Invoice.objects.select_related('customer', 'currency')
    serializer_class = InvoiceSerializer
    search_fields = ['invoice_number', 'customer__name', 'reference']
    filterset_fields = ['customer', 'status']
    ordering_fields = ['invoice_date', 'due_date', 'total_amount', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return InvoiceListSerializer
        return InvoiceSerializer
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue invoices."""
        queryset = self.get_queryset().filter(status='overdue')
        serializer = InvoiceListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get invoice summary statistics."""
        queryset = self.get_queryset()
        
        summary = {
            'total_count': queryset.count(),
            'total_amount': queryset.aggregate(total=Sum('total_amount'))['total'] or 0,
            'outstanding': queryset.filter(status__in=['sent', 'partial', 'overdue']).aggregate(total=Sum('balance_due'))['total'] or 0,
            'overdue_count': queryset.filter(status='overdue').count(),
            'by_status': list(queryset.values('status').annotate(
                count=Count('id'),
                total=Sum('total_amount')
            ))
        }
        
        return Response(summary)


class PaymentViewSet(ERPBaseViewSet):
    """API endpoint for payments."""
    queryset = Payment.objects.select_related('customer', 'payment_method')
    serializer_class = PaymentSerializer
    search_fields = ['payment_number', 'customer__name', 'reference']
    filterset_fields = ['customer', 'payment_method']
    ordering_fields = ['payment_date', 'amount', 'created_at']


class ExpenseCategoryViewSet(ERPBaseViewSet):
    """API endpoint for expense categories."""
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    filterset_fields = ['is_active', 'parent']


class ExpenseViewSet(ERPBaseViewSet):
    """API endpoint for expenses."""
    queryset = Expense.objects.select_related('category', 'submitted_by', 'approved_by')
    serializer_class = ExpenseSerializer
    search_fields = ['expense_number', 'description']
    filterset_fields = ['category', 'status', 'submitted_by']
    ordering_fields = ['expense_date', 'total_amount', 'created_at']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an expense."""
        expense = self.get_object()
        if expense.status != 'pending':
            return Response({'detail': 'Can only approve pending expenses.'}, status=status.HTTP_400_BAD_REQUEST)
        
        expense.status = 'approved'
        if hasattr(request.user, 'employee_profile'):
            expense.approved_by = request.user.employee_profile
        expense.approved_at = timezone.now()
        expense.save()
        
        serializer = self.get_serializer(expense)
        return Response(serializer.data)


# =============================================================================
# Supplier ViewSets
# =============================================================================

class SupplierViewSet(ERPBaseViewSet):
    """API endpoint for suppliers."""
    queryset = Supplier.objects.prefetch_related('contacts')
    serializer_class = SupplierSerializer
    search_fields = ['name', 'email', 'supplier_id']
    filterset_fields = ['supplier_type', 'is_active']
    ordering_fields = ['name', 'rating', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SupplierListSerializer
        return SupplierSerializer
    
    @action(detail=True, methods=['get'])
    def purchase_orders(self, request, pk=None):
        """Get purchase orders for a supplier."""
        supplier = self.get_object()
        pos = supplier.purchase_orders.order_by('-po_date')
        serializer = PurchaseOrderSerializer(pos, many=True)
        return Response(serializer.data)


class SupplierContactViewSet(ERPBaseViewSet):
    """API endpoint for supplier contacts."""
    queryset = SupplierContact.objects.select_related('supplier')
    serializer_class = SupplierContactSerializer
    filterset_fields = ['supplier', 'is_primary']


class PurchaseOrderViewSet(ERPBaseViewSet):
    """API endpoint for purchase orders."""
    queryset = PurchaseOrder.objects.select_related('supplier')
    serializer_class = PurchaseOrderSerializer
    search_fields = ['po_number', 'supplier__name']
    filterset_fields = ['supplier', 'status']
    ordering_fields = ['po_date', 'total_amount', 'created_at']


# =============================================================================
# CRM ViewSets
# =============================================================================

class LeadViewSet(ERPBaseViewSet):
    """API endpoint for leads."""
    queryset = Lead.objects.select_related('assigned_to', 'converted_customer')
    serializer_class = LeadSerializer
    search_fields = ['first_name', 'last_name', 'email', 'lead_number', 'company_name']
    filterset_fields = ['source', 'status', 'assigned_to']
    ordering_fields = ['created_at', 'estimated_value', 'next_follow_up']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return LeadListSerializer
        return LeadSerializer
    
    @action(detail=True, methods=['post'])
    def log_activity(self, request, pk=None):
        """Log an activity for a lead."""
        lead = self.get_object()
        serializer = LeadActivitySerializer(data={
            **request.data,
            'lead': lead.pk,
            'performed_by': getattr(request.user, 'employee_profile', None)
        })
        serializer.is_valid(raise_exception=True)
        serializer.save(lead=lead)
        
        # Update last contacted
        lead.last_contacted = timezone.now()
        lead.save(update_fields=['last_contacted'])
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Convert a lead to a customer."""
        lead = self.get_object()
        if lead.status == 'won':
            return Response({'detail': 'Lead already converted.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create customer from lead data
        customer = Customer.objects.create(
            company=lead.company,
            name=f"{lead.first_name} {lead.last_name}",
            email=lead.email,
            phone=lead.phone,
            mobile=lead.mobile,
            notes=lead.notes,
        )
        
        # Update lead
        lead.status = 'won'
        lead.converted_customer = customer
        lead.converted_at = timezone.now()
        lead.save()
        
        return Response({
            'lead': LeadSerializer(lead).data,
            'customer': CustomerSerializer(customer).data,
        })
    
    @action(detail=False, methods=['get'])
    def pipeline(self, request):
        """Get lead pipeline summary."""
        queryset = self.get_queryset()
        
        pipeline = queryset.values('status').annotate(
            count=Count('id'),
            total_value=Sum('estimated_value')
        ).order_by('status')
        
        return Response(list(pipeline))


class LeadActivityViewSet(ERPBaseViewSet):
    """API endpoint for lead activities."""
    queryset = LeadActivity.objects.select_related('lead', 'performed_by')
    serializer_class = LeadActivitySerializer
    filterset_fields = ['lead', 'activity_type']
    ordering_fields = ['activity_date', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        company = self.get_company()
        if company:
            return queryset.filter(lead__company=company)
        return queryset


class CustomerInteractionViewSet(ERPBaseViewSet):
    """API endpoint for customer interactions."""
    queryset = CustomerInteraction.objects.select_related('customer', 'performed_by')
    serializer_class = CustomerInteractionSerializer
    filterset_fields = ['customer', 'interaction_type']
    ordering_fields = ['interaction_date', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        company = self.get_company()
        if company:
            return queryset.filter(customer__company=company)
        return queryset


class CampaignViewSet(ERPBaseViewSet):
    """API endpoint for marketing campaigns."""
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    search_fields = ['name']
    filterset_fields = ['campaign_type', 'status']
    ordering_fields = ['start_date', 'budget', 'created_at']
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get campaign performance metrics."""
        campaign = self.get_object()
        
        leads_count = campaign.leads.count()
        converted_count = campaign.leads.filter(lead__status='won').count()
        
        return Response({
            'campaign': CampaignSerializer(campaign).data,
            'leads_generated': leads_count,
            'conversions': converted_count,
            'conversion_rate': (converted_count / leads_count * 100) if leads_count > 0 else 0,
            'roi': ((campaign.actual_revenue - campaign.actual_cost) / campaign.actual_cost * 100) if campaign.actual_cost > 0 else 0,
        })


class TaskViewSet(ERPBaseViewSet):
    """API endpoint for tasks."""
    queryset = Task.objects.select_related('assigned_to', 'related_lead', 'related_customer')
    serializer_class = TaskSerializer
    search_fields = ['title', 'description']
    filterset_fields = ['status', 'priority', 'assigned_to']
    ordering_fields = ['due_date', 'priority', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TaskListSerializer
        return TaskSerializer
    
    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        """Get tasks assigned to current user."""
        if hasattr(request.user, 'employee_profile'):
            queryset = self.get_queryset().filter(assigned_to=request.user.employee_profile)
            serializer = TaskListSerializer(queryset, many=True)
            return Response(serializer.data)
        return Response([])
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue tasks."""
        queryset = self.get_queryset().filter(
            status__in=['todo', 'in_progress'],
            due_date__lt=timezone.now()
        )
        serializer = TaskListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Add a comment to a task."""
        task = self.get_object()
        serializer = TaskCommentSerializer(data={
            **request.data,
            'task': task.pk,
        })
        serializer.is_valid(raise_exception=True)
        
        author = getattr(request.user, 'employee_profile', None)
        serializer.save(task=task, author=author)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TaskCommentViewSet(viewsets.ModelViewSet):
    """API endpoint for task comments."""
    queryset = TaskComment.objects.select_related('task', 'author')
    serializer_class = TaskCommentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['task']


# =============================================================================
# Services ViewSets
# =============================================================================

class ServiceCategoryViewSet(ERPBaseViewSet):
    """API endpoint for service categories."""
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    filterset_fields = ['is_active', 'parent']


class ServicePricingViewSet(ERPBaseViewSet):
    """API endpoint for service pricing."""
    queryset = ServicePricing.objects.select_related('category').prefetch_related('tiers')
    serializer_class = ServicePricingSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['category', 'pricing_type', 'is_active']


class QuoteViewSet(ERPBaseViewSet):
    """API endpoint for quotes."""
    queryset = Quote.objects.select_related('customer', 'lead', 'currency')
    serializer_class = QuoteSerializer
    search_fields = ['quote_number', 'customer__name', 'reference']
    filterset_fields = ['customer', 'lead', 'status']
    ordering_fields = ['quote_date', 'total_amount', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return QuoteListSerializer
        return QuoteSerializer
    
    @action(detail=True, methods=['post'])
    def convert_to_invoice(self, request, pk=None):
        """Convert a quote to an invoice."""
        quote = self.get_object()
        if quote.status != 'accepted':
            return Response({'detail': 'Can only convert accepted quotes.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if quote.converted_invoice:
            return Response({'detail': 'Quote already converted.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create invoice from quote
        invoice = Invoice.objects.create(
            company=quote.company,
            customer=quote.customer,
            currency=quote.currency,
            reference=f"From Quote {quote.quote_number}",
            subtotal_amount=quote.subtotal_amount,
            discount_amount=quote.discount_amount,
            tax_amount=quote.tax_amount,
            total_amount=quote.total_amount,
            notes=quote.notes,
            terms=quote.terms,
        )
        
        # Copy lines
        for line in quote.lines.all():
            InvoiceLine.objects.create(
                invoice=invoice,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
                tax_rate=line.tax_rate,
            )
        
        # Update quote
        quote.converted_invoice = invoice
        quote.save()
        
        return Response({
            'quote': QuoteSerializer(quote).data,
            'invoice': InvoiceSerializer(invoice).data,
        })


# =============================================================================
# Reporting ViewSets
# =============================================================================

class DashboardViewSet(ERPBaseViewSet):
    """API endpoint for dashboards."""
    queryset = Dashboard.objects.prefetch_related('widgets')
    serializer_class = DashboardSerializer
    filterset_fields = ['is_default', 'created_by']


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    """API endpoint for dashboard widgets."""
    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['dashboard', 'widget_type']


class KPIViewSet(ERPBaseViewSet):
    """API endpoint for KPIs."""
    queryset = KPI.objects.prefetch_related('values')
    serializer_class = KPISerializer
    search_fields = ['name', 'code']
    filterset_fields = ['category', 'is_active']
    
    @action(detail=True, methods=['post'])
    def record_value(self, request, pk=None):
        """Record a new KPI value."""
        kpi = self.get_object()
        value = request.data.get('value')
        date = request.data.get('date', timezone.now().date())
        
        kpi_value = KPIValue.objects.create(
            kpi=kpi,
            value=value,
            date=date
        )
        
        from .serializers import KPIValueSerializer
        return Response(KPIValueSerializer(kpi_value).data, status=status.HTTP_201_CREATED)


# =============================================================================
# Audit ViewSets
# =============================================================================

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for audit logs (read-only)."""
    queryset = AuditLog.objects.select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'action', 'content_type']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']


class NotificationViewSet(viewsets.ModelViewSet):
    """API endpoint for user notifications."""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications."""
        queryset = self.get_queryset().filter(is_read=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response(self.get_serializer(notification).data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'detail': 'All notifications marked as read.'})
