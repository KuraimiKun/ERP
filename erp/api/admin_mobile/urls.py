"""URL configuration for the admin mobile API.

Mounted by ``erpproject.urls`` at ``/api/mobile/admin/v1/``.  Keeping an
explicit ``v1/`` segment from day one means future breaking changes can
ship at ``/api/mobile/admin/v2/`` without disturbing existing clients.
"""

from django.urls import path

from .views import auth as auth_views

app_name = 'admin_mobile'

urlpatterns = [
    # ── Auth & session ────────────────────────────────────────────────
    # Smoke-test endpoint. Real login/logout/change-password/devices
    # arrive in the Auth+Dashboard PR (plan step 2).
    path('auth/me/', auth_views.admin_me, name='auth-me'),
]
