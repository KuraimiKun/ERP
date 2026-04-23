"""Auth endpoints: login, logout."""

from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from tenants.routers import get_tenant_db_alias, set_current_db_alias

from ..base import _employee_json, _error, _get_employee


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def mobile_login(request):
    """
    Authenticate with email + password.
    Returns token, employee data, permissions, company info, and tenant_db.
    """
    email = request.data.get("email", "").strip()
    password = request.data.get("password", "")

    if not email or not password:
        return _error("Email and password are required.")

    user = authenticate(request, username=email, password=password)
    if not user:
        return _error("Invalid email or password.", 401)

    if not user.is_approved:
        return _error("Your account is not yet approved.", 403)

    # Resolve tenant DB
    db_alias = get_tenant_db_alias(user)
    if db_alias == "default":
        return _error("No database assigned to your account.", 403)

    # Set tenant context to look up employee
    set_current_db_alias(db_alias)

    employee = _get_employee(user)
    if not employee:
        return _error("No employee profile found for your account.", 404)

    # Tokens live in the default DB — force it explicitly since tenant
    # context is already set and the router would send it to the wrong DB.
    token, _ = Token.objects.using("default").get_or_create(user=user)

    company = employee.company
    return Response(
        {
            "token": token.key,
            "employee": _employee_json(employee),
            "company": {
                "id": company.pk,
                "name": company.name,
                "name_ar": company.name_ar if hasattr(company, "name_ar") else "",
                "logo_url": company.logo.url if hasattr(company, "logo") and company.logo else "",
            },
            "tenant_db": db_alias,
        }
    )


@api_view(["POST"])
def mobile_logout(request):
    """Delete the current auth token."""
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    return Response({"success": True})
