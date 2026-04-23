"""
ERP Admin – Company isolation mixin.

CompanyIsolatedAdmin scopes every queryset to the requesting staff user's
own company.  Superusers always see the full dataset.

Usage
-----
1. Inherit from ``CompanyIsolatedAdmin`` instead of ``admin.ModelAdmin``.
2. If the model's company FK is not a direct field (e.g. the company is
   reached via a related model), set ``company_lookup`` on the class::

       class LeaveRequestAdmin(CompanyIsolatedAdmin, ...):
           company_lookup = 'employee__company'

3. For inline classes inherit from ``CompanyIsolatedInline`` instead of
   ``admin.TabularInline`` / ``admin.StackedInline`` to get company-scoped
   FK dropdowns inside the inline form.
"""

from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist


# Sentinel: non-superuser staff with no employee profile → return qs.none()
_UNSET = object()


class CompanyIsolatedAdmin(admin.ModelAdmin):
    """
    Base ModelAdmin that restricts every queryset to the requesting user's
    company.

    * Superusers  → no filter applied, full dataset visible.
    * Staff with an employee profile → only their company's data.
    * Staff without an employee profile → empty queryset (safe default).
    """

    company_lookup: str = "company"

    # ── company resolution ────────────────────────────────────────────────────

    def _get_company(self, request):
        """
        Return the company for the current admin user.

        Returns ``None`` for superusers (no filter), a ``Company`` instance
        for staff with an employee profile, or the ``_UNSET`` sentinel for
        staff without one (triggers an empty queryset).
        """
        if request.user.is_superuser:
            return None
        try:
            return request.user.employee_profile.company
        except (AttributeError, ObjectDoesNotExist):
            return _UNSET

    # ── queryset scoping ──────────────────────────────────────────────────────

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        company = self._get_company(request)
        if company is None:  # superuser — see everything
            return qs
        if company is _UNSET:  # staff with no company — see nothing
            return qs.none()
        return qs.filter(**{self.company_lookup: company})

    # ── auto-assign company on new objects ────────────────────────────────────

    def save_model(self, request, obj, form, change):
        if not change:
            company = self._get_company(request)
            if company is not None and company is not _UNSET and hasattr(obj, "company_id") and not obj.company_id:
                obj.company = company
        super().save_model(request, obj, form, change)

    # ── scope FK dropdowns to the user's company ──────────────────────────────

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        company = self._get_company(request)
        if company is not None and company is not _UNSET:
            related_model = db_field.related_model
            if hasattr(related_model, "company"):
                kwargs.setdefault(
                    "queryset",
                    related_model._default_manager.filter(company=company),
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CompanyIsolatedInline(admin.TabularInline):
    """
    Inline equivalent of ``CompanyIsolatedAdmin``.

    Does not filter the inline queryset (that is already scoped by the
    parent object), but it does scope FK dropdowns inside the inline form
    so staff cannot accidentally select objects from another company.
    """

    def _get_company(self, request):
        if request.user.is_superuser:
            return None
        try:
            return request.user.employee_profile.company
        except (AttributeError, ObjectDoesNotExist):
            return _UNSET

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        company = self._get_company(request)
        if company is not None and company is not _UNSET:
            related_model = db_field.related_model
            if hasattr(related_model, "company"):
                kwargs.setdefault(
                    "queryset",
                    related_model._default_manager.filter(company=company),
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
