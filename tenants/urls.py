"""
URL configuration for Tenant Management

Public-facing routes are defined here directly.
Platform admin routes are separated into the platform_admin package
and included under the 'platform-admin/' prefix.
"""

from django.urls import path, include
from . import views
from . import views_tickets

app_name = 'tenants'

urlpatterns = [
    # ── Public Routes ──────────────────────────────────────────────────────
    path('', views.home, name='home'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),

    # Status pages
    path('pending/', views.pending_approval_view, name='pending_approval'),
    path('rejected/', views.rejected_view, name='rejected'),
    path('no-database/', views.no_database_view, name='no_database'),

    # Profile
    path('profile/', views.profile_view, name='profile'),

    # Employee Self-Registration (public)
    path('register/<str:token>/', views.employee_register_view, name='employee_register'),

    # ── Support Tickets (Tenant Side) ──────────────────────────────────────
    path('support/', views_tickets.tenant_ticket_list, name='tenant_ticket_list'),
    path('support/create/', views_tickets.tenant_ticket_create, name='tenant_ticket_create'),
    path('support/<uuid:pk>/', views_tickets.tenant_ticket_detail, name='tenant_ticket_detail'),
    path('support/<uuid:pk>/reply/', views_tickets.tenant_ticket_reply, name='tenant_ticket_reply'),
    path('support/<uuid:pk>/close/', views_tickets.tenant_ticket_close, name='tenant_ticket_close'),
    path('support/<uuid:pk>/rate/', views_tickets.tenant_ticket_rate, name='tenant_ticket_rate'),
    path('support/<uuid:pk>/reopen/', views_tickets.tenant_ticket_reopen, name='tenant_ticket_reopen'),

    # ── Platform Admin (separated package) ─────────────────────────────────
    path('platform-admin/', include('tenants.platform_admin.urls')),
]
