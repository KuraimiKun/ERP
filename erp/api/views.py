"""
ERP API ViewSets

Django REST Framework ViewSets for the ERP system.
"""

import logging

from rest_framework import viewsets, status, filters

logger = logging.getLogger('erp.api')
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .permissions import IsCompanyUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from django.db import models
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
    ReportTemplate, GeneratedReport,
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
    InvoiceListSerializer, PaymentSerializer,
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
    ReportTemplateSerializer, ReportTemplateListSerializer, GeneratedReportSerializer,
    # Audit
    AuditLogSerializer, NotificationSerializer,
)


class ERPBaseViewSet(viewsets.ModelViewSet):
    """Base ViewSet with common functionality for ERP views."""
    permission_classes = [IsAuthenticated, IsCompanyUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    def get_company(self):
        """Get the current user's company, or raise 403 if they have no profile."""
        user = self.request.user
        if hasattr(user, 'employee_profile') and user.employee_profile:
            return user.employee_profile.company
        raise PermissionDenied('No employee profile found for this user.')

    def get_queryset(self):
        """Filter queryset by company."""
        queryset = super().get_queryset()
        company = self.get_company()
        if company and hasattr(queryset.model, 'company'):
            return queryset.filter(company=company)
        return queryset

    def perform_destroy(self, instance):
        """Soft-delete instead of hard-delete for all ERPBaseModel instances."""
        from erp.models.base import ERPBaseModel
        if isinstance(instance, ERPBaseModel):
            instance.soft_delete(self.request.user)
        else:
            instance.delete()


# =============================================================================
# Core ViewSets
# =============================================================================

class CurrencyViewSet(viewsets.ModelViewSet):
    """API endpoint for currencies."""
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name']
    filterset_fields = ['is_active', 'is_base']
    ordering_fields = ['code', 'name', 'exchange_rate']
    ordering = ['code']

    def get_permissions(self):
        # Currencies are global system config; only admins may write.
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminUser()]


class CompanyViewSet(viewsets.ModelViewSet):
    """API endpoint for companies."""
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'legal_name', 'email']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class DepartmentViewSet(ERPBaseViewSet):
    """API endpoint for departments."""
    queryset = Department.objects.select_related('parent', 'manager')
    serializer_class = DepartmentSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['is_active', 'parent']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']


class BranchViewSet(ERPBaseViewSet):
    """API endpoint for branches."""
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    search_fields = ['name', 'code', 'city']
    filterset_fields = ['is_active', 'is_headquarters', 'city', 'country']
    ordering_fields = ['name', 'city', 'created_at']
    ordering = ['name']


class FiscalYearViewSet(ERPBaseViewSet):
    """API endpoint for fiscal years."""
    queryset = FiscalYear.objects.all()
    serializer_class = FiscalYearSerializer
    search_fields = ['name']
    filterset_fields = ['is_current', 'is_closed']
    ordering_fields = ['start_date', 'end_date', 'name']
    ordering = ['-start_date']


# =============================================================================
# HR ViewSets
# =============================================================================

class EmployeeViewSet(ERPBaseViewSet):
    """API endpoint for employees."""
    queryset = Employee.objects.select_related('department', 'branch', 'reports_to')
    serializer_class = EmployeeSerializer
    search_fields = ['first_name', 'last_name', 'email', 'employee_id']
    filterset_fields = ['department', 'branch', 'employment_status', 'employment_type']
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
    search_fields = ['name', 'code']
    filterset_fields = ['is_active', 'is_paid', 'requires_approval']
    ordering_fields = ['name', 'days_allowed']
    ordering = ['name']

    def get_permissions(self):
        # Leave types are global lookup data; only admins may write.
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminUser()]


def _can_approve_for_employee(requesting_user, subject_employee):
    """
    Return True if requesting_user has management authority over subject_employee.

    Authorised if the requester is:
    - Django staff / superuser
    - Tenant owner or admin (DatabaseAssignment role in the default DB)
    - The direct line manager of the subject (Employee.reports_to)
    - The department manager of the subject's department (Department.manager)

    An employee is never authorised to approve their own requests.
    """
    if requesting_user.is_staff or requesting_user.is_superuser:
        return True

    approver = getattr(requesting_user, 'employee_profile', None)
    if approver is None:
        return False

    # An employee cannot approve their own requests.
    if approver.pk == subject_employee.pk:
        return False

    # Tenant owner / admin check via DatabaseAssignment.
    from tenants.models import DatabaseAssignment
    if DatabaseAssignment.objects.filter(
        user=requesting_user,
        role__in=['owner', 'admin'],
        is_active=True,
    ).exists():
        return True

    # Direct line manager (Employee.reports_to).
    if subject_employee.reports_to_id and subject_employee.reports_to_id == approver.pk:
        return True

    # Department manager (Department.manager).
    if subject_employee.department_id and Department.objects.filter(
        id=subject_employee.department_id,
        manager=approver,
    ).exists():
        return True

    return False


class LeaveRequestViewSet(ERPBaseViewSet):
    """API endpoint for leave requests."""
    queryset = LeaveRequest.objects.select_related('employee', 'leave_type', 'approved_by')
    serializer_class = LeaveRequestSerializer
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__employee_id']
    filterset_fields = ['employee', 'leave_type', 'status']
    ordering_fields = ['start_date', 'end_date', 'created_at', 'days_requested']
    ordering = ['-created_at']
    
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

        if not _can_approve_for_employee(request.user, leave_request.employee):
            raise PermissionDenied('You do not have permission to approve this leave request.')

        leave_request.status = 'approved'
        if hasattr(request.user, 'employee_profile'):
            leave_request.approved_by = request.user.employee_profile
        leave_request.approval_date = timezone.now()
        leave_request.save()

        serializer = self.get_serializer(leave_request)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a leave request."""
        leave_request = self.get_object()
        if leave_request.status != 'pending':
            return Response({'detail': 'Can only reject pending requests.'}, status=status.HTTP_400_BAD_REQUEST)

        if not _can_approve_for_employee(request.user, leave_request.employee):
            raise PermissionDenied('You do not have permission to reject this leave request.')

        leave_request.status = 'rejected'
        leave_request.approval_notes = request.data.get('reason', '')
        leave_request.save()

        serializer = self.get_serializer(leave_request)
        return Response(serializer.data)


class AttendanceViewSet(ERPBaseViewSet):
    """API endpoint for attendance records."""
    queryset = Attendance.objects.select_related('employee')
    serializer_class = AttendanceSerializer
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__employee_id']
    filterset_fields = ['employee', 'is_present', 'is_late', 'date']
    ordering_fields = ['date', 'check_in', 'check_out', 'hours_worked']
    ordering = ['-date']
    
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
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__employee_id']
    filterset_fields = ['employee', 'status']
    ordering_fields = ['period_start', 'period_end', 'payment_date', 'net_salary']
    ordering = ['-period_end']
    
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
    filterset_fields = ['account_type', 'is_active', 'is_system', 'parent']
    ordering_fields = ['code', 'name', 'account_type', 'current_balance']
    ordering = ['code']


class TaxRateViewSet(ERPBaseViewSet):
    """API endpoint for tax rates."""
    queryset = TaxRate.objects.all()
    serializer_class = TaxRateSerializer
    search_fields = ['name']
    filterset_fields = ['is_active', 'is_default']
    ordering_fields = ['name', 'rate']
    ordering = ['rate']


class PaymentMethodViewSet(ERPBaseViewSet):
    """API endpoint for payment methods."""
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['is_active']
    ordering_fields = ['name']
    ordering = ['name']


class CustomerViewSet(ERPBaseViewSet):
    """API endpoint for customers."""
    queryset = Customer.objects.select_related('currency')
    serializer_class = CustomerSerializer
    search_fields = ['name', 'email', 'customer_id', 'phone']
    filterset_fields = ['customer_type', 'is_active', 'assigned_to']
    ordering_fields = ['name', 'created_at', 'current_balance', 'customer_type']
    ordering = ['name']
    
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
            'balance': customer.current_balance,
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
    queryset = Invoice.objects.select_related('customer', 'currency').prefetch_related('lines')
    serializer_class = InvoiceSerializer
    search_fields = ['invoice_number', 'customer__name', 'reference']
    filterset_fields = ['customer', 'status', 'invoice_type']
    ordering_fields = ['invoice_date', 'due_date', 'total_amount', 'balance_due', 'created_at']
    ordering = ['-invoice_date']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return InvoiceListSerializer
        return InvoiceSerializer
    
    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 5))   # 5 minutes
    @method_decorator(vary_on_cookie)
    def overdue(self, request):
        """Get overdue invoices."""
        queryset = self.get_queryset().filter(status='overdue')
        serializer = InvoiceListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    @method_decorator(cache_page(60 * 5))   # 5 minutes
    @method_decorator(vary_on_cookie)
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
    filterset_fields = ['customer', 'payment_method', 'payment_type']
    ordering_fields = ['payment_date', 'amount', 'created_at']
    ordering = ['-payment_date']


class ExpenseCategoryViewSet(ERPBaseViewSet):
    """API endpoint for expense categories."""
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    search_fields = ['name', 'code']
    filterset_fields = ['is_active', 'parent']
    ordering_fields = ['name']
    ordering = ['name']


class ExpenseViewSet(ERPBaseViewSet):
    """API endpoint for expenses."""
    queryset = Expense.objects.select_related('category', 'employee', 'approved_by')
    serializer_class = ExpenseSerializer
    search_fields = ['expense_number', 'description']
    filterset_fields = ['category', 'status', 'employee']
    ordering_fields = ['expense_date', 'total_amount', 'created_at', 'status']
    ordering = ['-expense_date']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an expense."""
        expense = self.get_object()
        if expense.status != 'pending':
            return Response({'detail': 'Can only approve pending expenses.'}, status=status.HTTP_400_BAD_REQUEST)

        # When an expense has a submitting employee, verify the requester has
        # management authority over that employee.  Expenses without an employee
        # (e.g. company-level costs) can only be approved by staff/admins,
        # which is also enforced by _can_approve_for_employee when approver
        # is None.
        subject = expense.employee
        if subject is None:
            if not (request.user.is_staff or request.user.is_superuser):
                from tenants.models import DatabaseAssignment
                if not DatabaseAssignment.objects.filter(
                    user=request.user,
                    role__in=['owner', 'admin'],
                    is_active=True,
                ).exists():
                    raise PermissionDenied('You do not have permission to approve this expense.')
        elif not _can_approve_for_employee(request.user, subject):
            raise PermissionDenied('You do not have permission to approve this expense.')

        expense.status = 'approved'
        if hasattr(request.user, 'employee_profile'):
            expense.approved_by = request.user.employee_profile
        expense.approval_date = timezone.now()
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
    filterset_fields = ['supplier_type', 'is_active', 'rating']
    ordering_fields = ['name', 'rating', 'created_at', 'current_balance']
    ordering = ['name']
    
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
    search_fields = ['name', 'email']
    filterset_fields = ['supplier', 'is_primary']
    ordering_fields = ['name']
    ordering = ['name']


class PurchaseOrderViewSet(ERPBaseViewSet):
    """API endpoint for purchase orders."""
    queryset = PurchaseOrder.objects.select_related('supplier')
    serializer_class = PurchaseOrderSerializer
    search_fields = ['po_number', 'supplier__name', 'reference']
    filterset_fields = ['supplier', 'status']
    ordering_fields = ['po_date', 'expected_date', 'total_amount', 'created_at']
    ordering = ['-po_date']


# =============================================================================
# CRM ViewSets
# =============================================================================

class LeadViewSet(ERPBaseViewSet):
    """API endpoint for leads."""
    queryset = Lead.objects.select_related('assigned_to', 'converted_customer')
    serializer_class = LeadSerializer
    search_fields = ['first_name', 'last_name', 'email', 'lead_number', 'company_name']
    filterset_fields = ['source', 'status', 'assigned_to']
    ordering_fields = ['created_at', 'estimated_value', 'next_follow_up', 'expected_close_date']
    ordering = ['-created_at']
    
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
        lead.last_contact_date = timezone.now()
        lead.save(update_fields=['last_contact_date'])
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Convert a lead to a customer."""
        from django.db import transaction as db_transaction
        lead = self.get_object()
        if lead.status == 'won':
            return Response({'detail': 'Lead already converted.'}, status=status.HTTP_400_BAD_REQUEST)

        with db_transaction.atomic():
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
            lead.conversion_date = timezone.now()
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
    search_fields = ['subject', 'description']
    filterset_fields = ['lead', 'activity_type', 'is_completed']
    ordering_fields = ['activity_date', 'created_at']
    ordering = ['-activity_date']
    
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
    search_fields = ['subject', 'description']
    filterset_fields = ['customer', 'interaction_type', 'requires_follow_up']
    ordering_fields = ['interaction_date', 'created_at']
    ordering = ['-interaction_date']
    
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
    filterset_fields = ['campaign_type', 'status', 'owner']
    ordering_fields = ['start_date', 'end_date', 'budget', 'actual_cost', 'created_at']
    ordering = ['-start_date']
    
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
    ordering_fields = ['due_date', 'priority', 'created_at', 'status']
    ordering = ['-created_at']
    
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


class TaskCommentViewSet(ERPBaseViewSet):
    """API endpoint for task comments."""
    queryset = TaskComment.objects.select_related('task', 'author')
    serializer_class = TaskCommentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['task']
    ordering_fields = ['created_at']
    ordering = ['created_at']

    def get_queryset(self):
        company = self.get_company()
        return TaskComment.objects.select_related('task', 'author').filter(
            task__company=company
        )


# =============================================================================
# Services ViewSets
# =============================================================================

class ServiceCategoryViewSet(ERPBaseViewSet):
    """API endpoint for service categories."""
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    search_fields = ['name', 'code']
    filterset_fields = ['is_active', 'parent']
    ordering_fields = ['name', 'sort_order']
    ordering = ['sort_order', 'name']


class ServicePricingViewSet(ERPBaseViewSet):
    """API endpoint for service pricing."""
    queryset = ServicePricing.objects.select_related('category').prefetch_related('tiers')
    serializer_class = ServicePricingSerializer
    search_fields = ['name', 'code']
    filterset_fields = ['category', 'pricing_type', 'is_active']
    ordering_fields = ['name', 'base_price', 'code', 'created_at']
    ordering = ['name']


class QuoteViewSet(ERPBaseViewSet):
    """API endpoint for quotes."""
    queryset = Quote.objects.select_related('customer', 'lead', 'currency')
    serializer_class = QuoteSerializer
    search_fields = ['quote_number', 'customer__name', 'reference']
    filterset_fields = ['customer', 'lead', 'status']
    ordering_fields = ['quote_date', 'valid_until', 'total_amount', 'created_at']
    ordering = ['-quote_date']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return QuoteListSerializer
        return QuoteSerializer
    
    @action(detail=True, methods=['post'])
    def convert_to_invoice(self, request, pk=None):
        """Convert a quote to an invoice."""
        from django.db import transaction
        quote = self.get_object()
        if quote.status != 'accepted':
            return Response({'detail': 'Can only convert accepted quotes.'}, status=status.HTTP_400_BAD_REQUEST)

        if quote.converted_invoice:
            return Response({'detail': 'Quote already converted.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
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

            # Link quote to the new invoice
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
    search_fields = ['name']
    filterset_fields = ['is_default', 'created_by']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    """API endpoint for dashboard widgets."""
    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['dashboard', 'widget_type']
    ordering_fields = ['position', 'created_at']
    ordering = ['position']


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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['object_repr', 'changes']
    filterset_fields = ['user', 'action', 'content_type']
    ordering_fields = ['timestamp', 'action']
    ordering = ['-timestamp']


class NotificationViewSet(viewsets.ModelViewSet):
    """API endpoint for user notifications."""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return self.queryset.filter(recipient=self.request.user)
    
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


# =============================================================================
# Report Builder ViewSets
# =============================================================================

class ReportTemplateViewSet(ERPBaseViewSet):
    """CRUD for custom report templates + preview & generate actions."""
    queryset = ReportTemplate.objects.all()
    permission_classes = [IsAuthenticated]
    filterset_fields = ['report_type', 'is_active', 'is_public']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'report_type']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return ReportTemplateListSerializer
        return ReportTemplateSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # Show own templates + public ones
        return qs.filter(
            models.Q(created_by=user) | models.Q(is_public=True)
        )

    def perform_create(self, serializer):
        serializer.save(
            company=self.get_company(),
            created_by=self.request.user,
        )

    def perform_destroy(self, instance):
        if instance.is_system:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('System reports cannot be deleted.')
        instance.delete()

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """Quick preview: execute with limit=50 and return JSON rows."""
        template = self.get_object()
        config = template.configuration
        if not config or not config.get('data_source'):
            return Response({'error': 'Template has no configuration.'}, status=400)

        from erp.services.report_engine import execute_to_list
        try:
            result = execute_to_list(config, template.company, limit=50)
            return Response(result)
        except Exception as exc:
            logger.exception("Report preview failed: %s", exc)
            return Response({'error': 'Preview failed.'}, status=400)

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Kick off async report generation via Celery."""
        template = self.get_object()
        config = template.configuration
        if not config or not config.get('data_source'):
            return Response({'error': 'Template has no configuration.'}, status=400)

        from erp.tasks.report_tasks import user_has_running_report
        if user_has_running_report(request.user.pk):
            return Response(
                {'error': 'You already have a report generating. Please wait for it to finish.'},
                status=429,
            )

        output_format = request.data.get('output_format', template.default_format)
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')

        generated = GeneratedReport.objects.create(
            template=template,
            generated_by=request.user,
            output_format=output_format,
            date_from=date_from,
            date_to=date_to,
            parameters=request.data.get('parameters', {}),
            status=GeneratedReport.Status.PENDING,
        )

        from erp.tasks.report_tasks import generate_report
        from tenants.routers import get_current_db_alias
        generate_report.delay(generated.pk, db_alias=get_current_db_alias())

        return Response(
            GeneratedReportSerializer(generated, context={'request': request}).data,
            status=status.HTTP_202_ACCEPTED,
        )


class GeneratedReportViewSet(viewsets.ReadOnlyModelViewSet):
    """List & retrieve generated reports for the current user."""
    queryset = GeneratedReport.objects.select_related('template', 'generated_by')
    serializer_class = GeneratedReportSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template', 'status', 'output_format']
    ordering = ['-created_at']

    def get_queryset(self):
        return self.queryset.filter(generated_by=self.request.user)

    @action(detail=True, methods=['get'])
    def status_check(self, request, pk=None):
        """Lightweight status poll endpoint."""
        report = self.get_object()
        return Response({
            'id': report.pk,
            'status': report.status,
            'is_ready': report.is_ready,
            'row_count': report.row_count,
            'error_message': report.error_message,
            'download_url': request.build_absolute_uri(report.file.url) if report.file and report.is_ready else None,
        })

    def destroy(self, request, *args, **kwargs):
        """Allow users to delete their own generated reports."""
        instance = self.get_object()
        if instance.file:
            try:
                instance.file.delete(save=False)
            except Exception:
                pass
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DataSourceViewSet(viewsets.ViewSet):
    """Read-only endpoint returning available data sources + their fields."""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        from erp.services.report_builder import get_all_data_sources_meta
        return Response(get_all_data_sources_meta())
