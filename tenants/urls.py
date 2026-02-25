"""
URL configuration for Tenant Management
"""

from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    # Home
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
]
