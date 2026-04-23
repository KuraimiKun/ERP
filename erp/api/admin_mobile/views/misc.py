"""Notifications, audit log, settings, and search for the admin mobile API."""

from __future__ import annotations

from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from erp.api.admin_mobile.base import (
    AdminMobileBaseViewSet,
    AdminMobileReadOnlyViewSet,
)
from erp.api.admin_mobile.pagination import AdminMobilePagination
from erp.api.admin_mobile.serializers import (
    AuditLogMobileSerializer,
    CompanyMobileSerializer,
    CurrencyMobileSerializer,
    CustomerMobileListSerializer,
    EmployeeMobileListSerializer,
    FiscalYearMobileSerializer,
    InvoiceMobileListSerializer,
    NotificationMobileSerializer,
    ProductMobileListSerializer,
)
from erp.api.permissions import DefaultDbTokenAuthentication, IsCompanyAdmin

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationViewSet(viewsets.GenericViewSet):
    """Read-only notification inbox + mark-read actions."""

    authentication_classes = [DefaultDbTokenAuthentication]
    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    pagination_class = AdminMobilePagination
    serializer_class = NotificationMobileSerializer

    def get_queryset(self):
        from erp.models import Notification
        return Notification.objects.filter(recipient=self.request.user).order_by(
            '-created_at',
        )

    @extend_schema(tags=['admin-mobile'], summary='List notifications')
    def list(self, request):
        qs = self.get_queryset()
        unread_only = request.query_params.get('unread') in ('1', 'true', 'True')
        if unread_only:
            qs = qs.filter(is_read=False)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        tags=['admin-mobile'],
        summary='Mark selected notifications as read',
        request=inline_serializer(
            name='AdminNotificationReadRequest',
            fields={'ids': serializers.ListField(child=serializers.IntegerField())},
        ),
    )
    @action(detail=False, methods=['post'], url_path='read')
    def mark_read(self, request):
        ids = request.data.get('ids') or []
        if not isinstance(ids, list):
            return Response({'detail': 'ids must be a list of integers.'}, status=400)
        updated = self.get_queryset().filter(id__in=ids, is_read=False).update(
            is_read=True, read_at=timezone.now(),
        )
        return Response({'updated': updated})

    @extend_schema(tags=['admin-mobile'], summary='Mark all notifications as read')
    @action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True, read_at=timezone.now(),
        )
        return Response({'updated': updated})

    @extend_schema(tags=['admin-mobile'], summary='Unread notification count')
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'count': count})


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLogViewSet(AdminMobileReadOnlyViewSet):
    serializer_class = AuditLogMobileSerializer
    filterset_fields = ['action', 'user']
    ordering = ['-created_at']

    def get_queryset(self):
        from erp.models import AuditLog
        qs = AuditLog.objects.select_related('user', 'content_type').order_by('-created_at')

        model_name = self.request.query_params.get('model')
        if model_name:
            ct = ContentType.objects.filter(model=model_name.lower()).first()
            if ct:
                qs = qs.filter(content_type=ct)
            else:
                qs = qs.none()

        since_raw = self.request.query_params.get('since')
        if since_raw:
            try:
                since = datetime.fromisoformat(since_raw)
                qs = qs.filter(created_at__gte=since)
            except ValueError:
                pass

        actor = self.request.query_params.get('actor')
        if actor:
            qs = qs.filter(user_id=actor)

        return qs


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


_COMPANY_WRITABLE_FIELDS = {'name', 'name_ar', 'email', 'phone', 'address', 'city', 'country'}


@extend_schema(tags=['admin-mobile'], summary='Retrieve or update the company profile')
@api_view(['GET', 'PATCH'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def company_detail(request):
    """GET → current company. PATCH → update whitelisted fields only."""
    employee = getattr(request.user, 'employee_profile', None)
    if employee is None or employee.company is None:
        return Response({'detail': 'No company for user.'}, status=404)
    company = employee.company

    if request.method == 'GET':
        return Response(CompanyMobileSerializer(company).data)

    # PATCH — restrict to safe fields.
    data = {k: v for k, v in request.data.items() if k in _COMPANY_WRITABLE_FIELDS}
    if not data:
        return Response(
            {'detail': f'No writable fields in request. Allowed: {sorted(_COMPANY_WRITABLE_FIELDS)}'},
            status=400,
        )
    serializer = CompanyMobileSerializer(company, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@extend_schema(tags=['admin-mobile'], summary='Feature flags for the Flutter app')
@api_view(['GET'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def feature_flags(request):
    employee = getattr(request.user, 'employee_profile', None)
    company = getattr(employee, 'company', None) if employee else None
    return Response({
        'ai_enabled': bool(getattr(company, 'ai_enabled', False)) if company else False,
    })


class FiscalYearReadOnlyViewSet(AdminMobileReadOnlyViewSet):
    serializer_class = FiscalYearMobileSerializer
    filterset_fields = ['is_current', 'is_closed']
    ordering = ['-start_date']

    def get_queryset(self):
        from erp.models import FiscalYear
        return FiscalYear.objects.all()


class CurrencyReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """Currencies are company-agnostic so they bypass the company filter."""

    authentication_classes = [DefaultDbTokenAuthentication]
    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    pagination_class = AdminMobilePagination
    serializer_class = CurrencyMobileSerializer
    filterset_fields = ['is_active', 'is_base']

    def get_queryset(self):
        from erp.models import Currency
        return Currency.objects.all()


# ---------------------------------------------------------------------------
# Federated search
# ---------------------------------------------------------------------------


_SEARCH_TYPES = {'employee', 'customer', 'product', 'invoice'}
_PER_TYPE_CAP = 10


@extend_schema(
    tags=['admin-mobile'],
    summary='Federated search across employees, customers, products, invoices',
    parameters=[
        OpenApiParameter('q', str, description='Search query (required)'),
        OpenApiParameter(
            'types', str,
            description=(
                f'Comma-separated subset of {sorted(_SEARCH_TYPES)}. '
                'Omit to search all types.'
            ),
        ),
    ],
)
@api_view(['GET'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def search(request):
    from erp.models import Customer, Employee, Invoice, Product

    q = (request.query_params.get('q') or '').strip()
    if not q:
        return Response({'detail': 'Query parameter q is required.'}, status=400)

    types_raw = request.query_params.get('types')
    if types_raw:
        requested = {t.strip() for t in types_raw.split(',') if t.strip()}
        invalid = requested - _SEARCH_TYPES
        if invalid:
            return Response(
                {'detail': f'Unknown type(s): {sorted(invalid)}.'}, status=400,
            )
        active = requested
    else:
        active = set(_SEARCH_TYPES)

    employee = getattr(request.user, 'employee_profile', None)
    company = employee.company if employee and employee.company_id else None

    result = {}

    if 'employee' in active and company:
        qs = Employee.objects.filter(
            Q(company=company)
            & (
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(employee_id__icontains=q)
            )
        )[:_PER_TYPE_CAP]
        result['employee'] = EmployeeMobileListSerializer(qs, many=True).data

    if 'customer' in active and company:
        qs = Customer.objects.filter(
            Q(company=company)
            & (
                Q(name__icontains=q)
                | Q(email__icontains=q)
                | Q(customer_id__icontains=q)
                | Q(phone__icontains=q)
            )
        )[:_PER_TYPE_CAP]
        result['customer'] = CustomerMobileListSerializer(qs, many=True).data

    if 'product' in active and company:
        qs = Product.objects.filter(
            Q(company=company) & (Q(name__icontains=q) | Q(sku__icontains=q))
        )[:_PER_TYPE_CAP]
        result['product'] = ProductMobileListSerializer(qs, many=True).data

    if 'invoice' in active and company:
        qs = Invoice.objects.filter(
            Q(company=company)
            & (Q(invoice_number__icontains=q) | Q(customer__name__icontains=q))
        )[:_PER_TYPE_CAP]
        result['invoice'] = InvoiceMobileListSerializer(qs, many=True).data

    return Response({'q': q, 'types': sorted(active), 'results': result})
