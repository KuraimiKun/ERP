"""
Custom DRF permission classes for the ERP system.

These complement the global IsAuthenticated default with finer-grained
checks that enforce company isolation, AI feature availability, and
finance-specific access control.
"""

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import BasePermission


class DefaultDbTokenAuthentication(TokenAuthentication):
    """Token authentication that always reads from the default DB.

    DRF's stock TokenAuthentication uses the active DB router, which
    follows the tenant context set by TenantMiddleware. Since authtoken
    lives only in the default DB, every authenticated mobile request
    would fail with 'relation authtoken_token does not exist' in the
    tenant DB. Forcing .using('default') here fixes that.
    """

    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.using("default").select_related("user").get(key=key)
        except model.DoesNotExist:
            from rest_framework import exceptions

            raise exceptions.AuthenticationFailed("Invalid token.")

        if not token.user.is_active:
            from rest_framework import exceptions

            raise exceptions.AuthenticationFailed("User inactive or deleted.")

        return (token.user, token)


class IsCompanyUser(BasePermission):
    """Allow access only when the request user belongs to a company.

    Ensures the user has an employee_profile attached to a company so the
    tenant context is always well-defined before accessing company data.
    """

    message = "Your account is not associated with any company."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        # Primary: user has an employee profile linked to a company
        try:
            if (
                hasattr(request.user, "employee_profile")
                and request.user.employee_profile is not None
                and request.user.employee_profile.company_id is not None
            ):
                return True
        except Exception:
            pass
        # Fallback: user is the company owner (created_by), matching get_user_company()
        from erp.models import Company

        return Company.objects.filter(created_by=request.user).exists()


class IsAIEnabled(BasePermission):
    """Allow access only when AI features are enabled for the user's company.

    Apply to AI trigger endpoints and the natural-language assistant so
    companies that have disabled AI or have no API key cannot access them.
    """

    message = "AI features are not enabled for your company."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        try:
            company = request.user.employee_profile.company
            return bool(getattr(company, "ai_enabled", False))
        except AttributeError:
            return False


class IsFinanceManager(BasePermission):
    """Allow write access only to users with the finance_manager role.

    Read access (GET/HEAD/OPTIONS) is allowed for all authenticated company
    users; mutating actions (POST/PUT/PATCH/DELETE) require finance_manager.

    The role is checked via the employee_profile.role field.  Adjust the
    role name to match your actual role taxonomy if it differs.
    """

    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
    FINANCE_ROLES = frozenset({"finance_manager", "cfo", "accountant", "admin"})
    message = "Finance write access requires the Finance Manager role."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in self.SAFE_METHODS:
            return True
        try:
            role = getattr(request.user.employee_profile, "role", "") or ""
            return role.lower() in self.FINANCE_ROLES or request.user.is_staff
        except AttributeError:
            return request.user.is_staff


class IsAdminOrReadOnly(BasePermission):
    """Read access for all authenticated users; write access for staff only."""

    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in self.SAFE_METHODS or request.user.is_staff


class IsCompanyAdmin(BasePermission):
    """Allow access only to tenant admins/owners (admin mobile API gate).

    A user is considered an admin when any of the following is true:

    * ``request.user.is_superuser`` (platform support staff).
    * They have an ``employee_profile`` linked to a company *and* an active
      ``tenants.DatabaseAssignment`` with ``role in {'owner', 'admin'}``.

    This mirrors the pattern already used by ``_can_approve_for_employee`` in
    ``erp/api/views.py`` — ``DatabaseAssignment`` is the canonical source of
    truth for "this user administers this tenant DB" and lives in the default
    database alongside ``TenantUser`` / authtoken, so it works regardless of
    which tenant DB the current request is routed to.
    """

    ADMIN_ROLES = frozenset({"owner", "admin"})
    message = "Admin access required. Your account is not assigned the owner or admin role on this tenant."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.is_superuser:
            return True

        # The canonical source of truth is ``DatabaseAssignment``: a user
        # administers a tenant iff they have an active owner/admin row
        # for it.  An ``Employee`` is NOT required — tenant owners often
        # manage the company without being employed by it.
        from tenants.models import DatabaseAssignment

        return DatabaseAssignment.objects.filter(
            user=user,
            role__in=self.ADMIN_ROLES,
            is_active=True,
        ).exists()
