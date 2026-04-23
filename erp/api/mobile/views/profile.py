"""Profile and password endpoints."""

from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..base import _employee_json, _error, _get_employee


@api_view(["GET", "PATCH"])
def mobile_profile(request):
    """GET: employee profile. PATCH: update allowed fields."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if request.method == "PATCH":
        if not employee.portal_can_edit_profile:
            return _error("You do not have permission to edit your profile.", 403)

        allowed_fields = [
            "phone",
            "emergency_contact_name",
            "emergency_contact_phone",
            "address",
            "city",
            "country",
        ]
        updated = []
        for field in allowed_fields:
            if field in request.data:
                setattr(employee, field, request.data[field])
                updated.append(field)

        if updated:
            employee.save(update_fields=updated + ["updated_at"])

    data = _employee_json(employee)
    data.update(
        {
            "gender": employee.gender,
            "date_of_birth": employee.date_of_birth.isoformat() if employee.date_of_birth else None,
            "nationality": employee.nationality or "",
            "emergency_contact_name": employee.emergency_contact_name or "",
            "emergency_contact_phone": employee.emergency_contact_phone or "",
            "address": employee.address or "",
            "city": employee.city or "",
            "country": employee.country or "",
            "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
            "employment_type": employee.employment_type,
            "employment_status": employee.employment_status,
            "branch": employee.branch.name if employee.branch else "",
        }
    )
    return Response(data)


@api_view(["POST"])
def mobile_change_password(request):
    """Change password. Requires current_password, new_password, confirm_password."""
    current_password = request.data.get("current_password", "")
    new_password = request.data.get("new_password", "")
    confirm_password = request.data.get("confirm_password", "")

    if not current_password or not new_password:
        return _error("Current password and new password are required.")

    if not request.user.check_password(current_password):
        return _error("Current password is incorrect.")

    if new_password != confirm_password:
        return _error("New passwords do not match.")

    if len(new_password) < 8:
        return _error("New password must be at least 8 characters.")

    request.user.set_password(new_password)
    request.user.save()

    # Regenerate token
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    token = Token.objects.create(user=request.user)

    return Response({"success": True, "token": token.key})
