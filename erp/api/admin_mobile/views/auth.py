"""Auth endpoints for the admin mobile API.

Only the smoke-test ``/auth/me/`` endpoint is implemented in the
Foundation PR — login/logout/change-password/device-register land in the
subsequent Auth+Dashboard PR (step 2 of the plan).
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from erp.api.permissions import DefaultDbTokenAuthentication, IsCompanyAdmin
from tenants.models import DatabaseAssignment


def _resolve_admin_role(user) -> str:
    """Return the admin's tenant role for the UI badge ('owner'|'admin')."""
    if user.is_superuser:
        # Superusers don't necessarily have a DatabaseAssignment row.
        return 'owner'

    assignment = (
        DatabaseAssignment.objects
        .filter(user=user, is_active=True, role__in=['owner', 'admin'])
        .order_by('-assigned_at')
        .first()
    )
    return assignment.role if assignment else 'admin'


_AdminMeResponse = inline_serializer(
    name='AdminMeResponse',
    fields={
        'user': inline_serializer(
            name='AdminMeUser',
            fields={
                'id': serializers.IntegerField(),
                'email': serializers.EmailField(),
                'first_name': serializers.CharField(),
                'last_name': serializers.CharField(),
                'is_superuser': serializers.BooleanField(),
            },
        ),
        'employee': inline_serializer(
            name='AdminMeEmployee',
            fields={
                'id': serializers.IntegerField(),
                'employee_id': serializers.CharField(),
                'first_name': serializers.CharField(),
                'last_name': serializers.CharField(),
                'email': serializers.EmailField(),
                'job_title': serializers.CharField(),
            },
            allow_null=True,
        ),
        'company': inline_serializer(
            name='AdminMeCompany',
            fields={
                'id': serializers.IntegerField(),
                'name': serializers.CharField(),
                'name_ar': serializers.CharField(),
            },
            allow_null=True,
        ),
        'role': serializers.ChoiceField(choices=['owner', 'admin']),
    },
)


@extend_schema(
    tags=['admin-mobile'],
    summary='Get the authenticated admin profile',
    description=(
        'Smoke-test endpoint for the Flutter admin app. Returns the '
        'authenticated user, their linked employee profile, company, and '
        'tenant role. Requires a valid token AND the caller to hold an '
        'active owner/admin DatabaseAssignment (or be a superuser).'
    ),
    responses={200: _AdminMeResponse},
    examples=[
        OpenApiExample(
            'Admin user',
            value={
                'user': {
                    'id': 42,
                    'email': 'admin@example.com',
                    'first_name': 'Ada',
                    'last_name': 'Lovelace',
                    'is_superuser': False,
                },
                'employee': {
                    'id': 7,
                    'employee_id': 'EMP-0007',
                    'first_name': 'Ada',
                    'last_name': 'Lovelace',
                    'email': 'ada@example.com',
                    'job_title': 'CTO',
                },
                'company': {'id': 1, 'name': 'Acme', 'name_ar': ''},
                'role': 'admin',
            },
            response_only=True,
        ),
    ],
)
@api_view(['GET'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def admin_me(request):
    """Return the current admin user with minimal, mobile-shaped fields."""
    user = request.user
    employee = getattr(user, 'employee_profile', None)
    company = employee.company if employee and employee.company_id else None

    payload = {
        'user': {
            'id': user.pk,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_superuser': bool(user.is_superuser),
        },
        'employee': None,
        'company': None,
        'role': _resolve_admin_role(user),
    }

    if employee is not None:
        payload['employee'] = {
            'id': employee.pk,
            'employee_id': employee.employee_id,
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'email': employee.email,
            'job_title': employee.job_title or '',
        }

    if company is not None:
        payload['company'] = {
            'id': company.pk,
            'name': company.name,
            'name_ar': getattr(company, 'name_ar', '') or '',
        }

    return Response(payload)
