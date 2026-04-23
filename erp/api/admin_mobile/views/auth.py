"""Auth endpoints for the admin mobile API.

Login / logout / change-password / device registration for the Flutter
admin client.  The smoke-test ``auth/me/`` endpoint lives above.
"""

from __future__ import annotations

import logging

from django.contrib.auth import authenticate
from django.core.cache import cache
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from erp.api.permissions import DefaultDbTokenAuthentication, IsCompanyAdmin
from tenants.models import DatabaseAssignment
from tenants.routers import get_tenant_db_alias, set_current_db_alias

logger = logging.getLogger('erp.api.admin_mobile')

ADMIN_ROLES = frozenset({'owner', 'admin'})


def _error(msg, status_code=400):
    return Response({'detail': msg}, status=status_code)


def _resolve_admin_role(user) -> str:
    if user.is_superuser:
        return 'owner'
    assignment = (
        DatabaseAssignment.objects
        .filter(user=user, is_active=True, role__in=list(ADMIN_ROLES))
        .order_by('-assigned_at')
        .first()
    )
    return assignment.role if assignment else 'admin'


def _employee_payload(employee):
    if employee is None:
        return None
    return {
        'id': employee.pk,
        'employee_id': employee.employee_id,
        'first_name': employee.first_name,
        'last_name': employee.last_name,
        'email': employee.email,
        'job_title': employee.job_title or '',
    }


def _company_payload(company):
    if company is None:
        return None
    return {
        'id': company.pk,
        'name': company.name,
        'name_ar': getattr(company, 'name_ar', '') or '',
        'ai_enabled': bool(getattr(company, 'ai_enabled', False)),
    }


# ---------------------------------------------------------------------------
# POST /auth/login/
# ---------------------------------------------------------------------------


@extend_schema(
    tags=['admin-mobile'],
    summary='Authenticate as an admin and obtain a token',
    description=(
        'Admin-scoped login. Returns the auth token plus company, role, '
        'and feature flags. Non-admin users receive HTTP 403 — they must '
        'use the regular `/api/mobile/auth/login/` endpoint.'
    ),
    request=inline_serializer(
        name='AdminMobileLoginRequest',
        fields={
            'email': serializers.EmailField(),
            'password': serializers.CharField(),
        },
    ),
    responses={
        200: inline_serializer(
            name='AdminMobileLoginResponse',
            fields={
                'token': serializers.CharField(),
                'tenant_db': serializers.CharField(),
                'role': serializers.ChoiceField(choices=['owner', 'admin']),
                'employee': serializers.DictField(allow_null=True),
                'company': serializers.DictField(allow_null=True),
                'feature_flags': serializers.DictField(),
            },
        ),
    },
    examples=[
        OpenApiExample(
            'Success',
            value={
                'token': 'abcd1234',
                'tenant_db': 'tenant_uuid',
                'role': 'admin',
                'employee': {'id': 7, 'employee_id': 'EMP-0007', 'first_name': 'Ada',
                             'last_name': 'Lovelace', 'email': 'ada@example.com',
                             'job_title': 'CTO'},
                'company': {'id': 1, 'name': 'Acme', 'name_ar': '', 'ai_enabled': True},
                'feature_flags': {'ai_enabled': True},
            },
            response_only=True,
        ),
    ],
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def admin_login(request):
    email = (request.data.get('email') or '').strip()
    password = request.data.get('password') or ''

    if not email or not password:
        return _error('Email and password are required.', 400)

    user = authenticate(request, username=email, password=password)
    if not user:
        return _error('Invalid email or password.', 401)

    if not getattr(user, 'is_approved', True):
        return _error('Your account is not yet approved.', 403)

    # Non-admin? refuse access to the admin-mobile namespace.
    if not user.is_superuser:
        has_admin = DatabaseAssignment.objects.filter(
            user=user, is_active=True, role__in=list(ADMIN_ROLES),
        ).exists()
        if not has_admin:
            return _error(
                'Admin access required. Please use the employee mobile app '
                '(/api/mobile/auth/login/) instead.',
                403,
            )

    db_alias = get_tenant_db_alias(user)
    if db_alias == 'default' and not user.is_superuser:
        return _error('No database assigned to your account.', 403)

    if db_alias != 'default':
        set_current_db_alias(db_alias)

    # Locate the admin's Employee record. The shared helper back-fills
    # ``Employee.user_id`` so subsequent authenticated requests resolve
    # through ``user.employee_profile`` instead of the email fallback.
    from erp.api.admin_mobile.helpers import resolve_admin_employee
    employee = resolve_admin_employee(user)

    token, _ = Token.objects.using('default').get_or_create(user=user)

    company = employee.company if employee and employee.company_id else None
    feature_flags = {
        'ai_enabled': bool(getattr(company, 'ai_enabled', False)) if company else False,
    }

    return Response({
        'token': token.key,
        'tenant_db': db_alias,
        'role': _resolve_admin_role(user),
        'employee': _employee_payload(employee),
        'company': _company_payload(company),
        'feature_flags': feature_flags,
    })


# ---------------------------------------------------------------------------
# POST /auth/logout/
# ---------------------------------------------------------------------------


@extend_schema(
    tags=['admin-mobile'],
    summary='Log out the current admin (deletes the auth token)',
    request=None,
    responses={200: inline_serializer(
        name='AdminMobileLogoutResponse',
        fields={'detail': serializers.CharField()},
    )},
)
@api_view(['POST'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def admin_logout(request):
    try:
        Token.objects.using('default').filter(user=request.user).delete()
    except Exception:
        logger.warning('Failed to delete token for user %s', request.user.pk)
    return Response({'detail': 'Logged out.'})


# ---------------------------------------------------------------------------
# GET /auth/me/
# ---------------------------------------------------------------------------


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
        'employee': serializers.DictField(allow_null=True),
        'company': serializers.DictField(allow_null=True),
        'role': serializers.ChoiceField(choices=['owner', 'admin']),
    },
)


@extend_schema(
    tags=['admin-mobile'],
    summary='Get the authenticated admin profile',
    description=(
        'Returns the authenticated user, their linked employee profile, '
        'company, and tenant role.'
    ),
    responses={200: _AdminMeResponse},
)
@api_view(['GET'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def admin_me(request):
    user = request.user
    employee = getattr(user, 'employee_profile', None)
    company = employee.company if employee and employee.company_id else None

    return Response({
        'user': {
            'id': user.pk,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_superuser': bool(user.is_superuser),
        },
        'employee': _employee_payload(employee),
        'company': _company_payload(company),
        'role': _resolve_admin_role(user),
    })


# ---------------------------------------------------------------------------
# POST /auth/change-password/
# ---------------------------------------------------------------------------


@extend_schema(
    tags=['admin-mobile'],
    summary='Change the authenticated admin password',
    request=inline_serializer(
        name='AdminChangePasswordRequest',
        fields={
            'old_password': serializers.CharField(),
            'new_password': serializers.CharField(min_length=8),
        },
    ),
    responses={200: inline_serializer(
        name='AdminChangePasswordResponse',
        fields={'detail': serializers.CharField()},
    )},
)
@api_view(['POST'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def admin_change_password(request):
    # Simple per-user rate limit (5 attempts / 10 min) to frustrate brute
    # force of the old password.
    key = f'adminmobile:chgpw:{request.user.pk}'
    hits = cache.get(key, 0)
    if hits >= 5:
        return _error('Too many attempts. Try again later.', 429)
    cache.set(key, hits + 1, timeout=600)

    old_password = request.data.get('old_password') or ''
    new_password = request.data.get('new_password') or ''

    if not old_password or not new_password:
        return _error('old_password and new_password are required.', 400)
    if len(new_password) < 8:
        return _error('new_password must be at least 8 characters long.', 400)
    if not request.user.check_password(old_password):
        return _error('old_password is incorrect.', 400)

    request.user.set_password(new_password)
    request.user.save(update_fields=['password'])

    # Invalidate the old token so existing sessions have to re-login.
    Token.objects.using('default').filter(user=request.user).delete()
    token = Token.objects.using('default').create(user=request.user)

    # Reset the rate-limit counter on success.
    cache.delete(key)

    return Response({'detail': 'Password changed.', 'token': token.key})


# ---------------------------------------------------------------------------
# POST /devices/register/
# ---------------------------------------------------------------------------


@extend_schema(
    tags=['admin-mobile'],
    summary='Register a device token for future push notifications',
    description=(
        'Stores the (platform, token) pair in the per-user cache. Actual '
        'push dispatch is deferred to a future PR — this endpoint only '
        'captures the token so it is available when that lands.'
    ),
    request=inline_serializer(
        name='AdminDeviceRegisterRequest',
        fields={
            'token': serializers.CharField(),
            'platform': serializers.ChoiceField(choices=['ios', 'android']),
        },
    ),
    responses={200: inline_serializer(
        name='AdminDeviceRegisterResponse',
        fields={'detail': serializers.CharField()},
    )},
)
@api_view(['POST'])
@authentication_classes([DefaultDbTokenAuthentication])
@permission_classes([IsAuthenticated, IsCompanyAdmin])
def admin_device_register(request):
    device_token = (request.data.get('token') or '').strip()
    platform = (request.data.get('platform') or '').strip().lower()

    if not device_token:
        return _error('token is required.', 400)
    if platform not in ('ios', 'android'):
        return _error("platform must be 'ios' or 'android'.", 400)

    # Persist in cache (real dispatch model deferred to push-notification PR).
    key = f'adminmobile:device:{request.user.pk}:{platform}'
    cache.set(key, device_token, timeout=60 * 60 * 24 * 30)

    logger.info(
        'Admin mobile device registered',
        extra={'admin_action': 'device_register', 'platform': platform, 'user_id': request.user.pk},
    )
    return Response({'detail': 'Device registered.'})
