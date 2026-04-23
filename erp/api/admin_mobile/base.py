"""Base classes for admin-mobile viewsets.

``AdminMobileBaseViewSet`` is the single authoritative entry point for
admin-mobile CRUD endpoints.  Future per-domain viewsets (leaves,
invoices, etc.) subclass this to inherit:

* token + tenant-aware authentication (``DefaultDbTokenAuthentication``)
* the ``IsCompanyAdmin`` permission gate
* tenant-isolated querysets (filtered by
  ``request.user.employee_profile.company``)
* mobile-friendly pagination
* ``drf-spectacular`` tagging under the ``admin-mobile`` group

Subclasses only need to declare ``queryset`` and ``serializer_class``.
"""

from __future__ import annotations

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from erp.api.permissions import DefaultDbTokenAuthentication, IsCompanyAdmin

from .pagination import AdminMobilePagination

ADMIN_MOBILE_TAG = "admin-mobile"


@extend_schema(tags=[ADMIN_MOBILE_TAG])
class AdminMobileBaseViewSet(viewsets.ModelViewSet):
    """Company-scoped, admin-gated ModelViewSet for the mobile app."""

    authentication_classes = [DefaultDbTokenAuthentication]
    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    pagination_class = AdminMobilePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Subclasses should set these explicitly; kept here only to document them.
    queryset = None
    serializer_class = None

    # ------------------------------------------------------------------
    # Tenancy helpers
    # ------------------------------------------------------------------
    def get_company(self):
        """Return the admin's company, raising 403 when absent.

        Mirrors ``ERPBaseViewSet.get_company`` so every admin-mobile
        endpoint scopes data the same way as the web API.
        """
        from .helpers import resolve_admin_company

        company = resolve_admin_company(self.request.user)
        if company is None:
            raise PermissionDenied("No company found for this tenant.")
        return company

    def get_queryset(self):
        """Filter the base queryset by the admin's company when possible."""
        queryset = super().get_queryset()
        if queryset is None:
            return queryset
        company = self.get_company()
        if company and hasattr(queryset.model, "company"):
            return queryset.filter(company=company)
        return queryset

    # ------------------------------------------------------------------
    # Defence-in-depth: never let a write operation touch another tenant.
    # ------------------------------------------------------------------
    def perform_create(self, serializer):
        serializer.save(company=self.get_company())

    def perform_destroy(self, instance):
        """Soft-delete ERP models; hard-delete everything else."""
        from erp.models.base import ERPBaseModel

        if isinstance(instance, ERPBaseModel) and hasattr(instance, "soft_delete"):
            instance.soft_delete()
        else:
            instance.delete()


@extend_schema(tags=[ADMIN_MOBILE_TAG])
class AdminMobileReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only counterpart of ``AdminMobileBaseViewSet``.

    Used for reference data (accounts, currencies, fiscal years, …) where
    the admin mobile app needs to list/inspect but mutation happens via
    the web portal.
    """

    authentication_classes = [DefaultDbTokenAuthentication]
    permission_classes = [IsAuthenticated, IsCompanyAdmin]
    pagination_class = AdminMobilePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    queryset = None
    serializer_class = None

    def get_company(self):
        from .helpers import resolve_admin_company

        company = resolve_admin_company(self.request.user)
        if company is None:
            raise PermissionDenied("No company found for this tenant.")
        return company

    def get_queryset(self):
        queryset = super().get_queryset()
        if queryset is None:
            return queryset
        company = self.get_company()
        if company and hasattr(queryset.model, "company"):
            return queryset.filter(company=company)
        return queryset
