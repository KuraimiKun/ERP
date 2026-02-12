"""
Views for Tenant Management

Handles user signup, login, and status pages.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .forms import SignUpForm, LoginForm
from .models import TenantUser


def home(request):
    """Home page - redirect based on auth status."""
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin:index')
        if request.user.is_approved:
            if request.user.assigned_database:
                return redirect('erp:dashboard')
            return redirect('tenants:no_database')
        if request.user.approval_status == 'pending':
            return redirect('tenants:pending_approval')
        if request.user.approval_status == 'rejected':
            return redirect('tenants:rejected')
    return render(request, 'tenants/home.html')


@require_http_methods(["GET", "POST"])
def signup_view(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('tenants:home')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_approved = False
            user.approval_status = 'pending'
            user.save()
            
            # Log the user in after signup
            login(request, user)
            
            messages.success(
                request,
                'Your account has been created successfully. '
                'Please wait for admin approval.'
            )
            return redirect('tenants:pending_approval')
    else:
        form = SignUpForm()
    
    return render(request, 'tenants/signup.html', {'form': form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('tenants:home')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Check user status
            if user.is_staff:
                return redirect('admin:index')
            if not user.is_approved:
                if user.approval_status == 'pending':
                    return redirect('tenants:pending_approval')
                elif user.approval_status == 'rejected':
                    return redirect('tenants:rejected')
                elif user.approval_status == 'suspended':
                    logout(request)
                    messages.error(request, 'Your account has been suspended.')
                    return redirect('tenants:login')
            
            # Redirect to ERP dashboard or next URL
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('erp:dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'tenants/login.html', {'form': form})


def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('tenants:home')


@login_required
def pending_approval_view(request):
    """Page shown to users waiting for approval."""
    if request.user.is_approved:
        return redirect('erp:dashboard')
    if request.user.approval_status == 'rejected':
        return redirect('tenants:rejected')
    
    return render(request, 'tenants/pending_approval.html')


@login_required
def rejected_view(request):
    """Page shown to users whose application was rejected."""
    if request.user.is_approved:
        return redirect('erp:dashboard')
    if request.user.approval_status == 'pending':
        return redirect('tenants:pending_approval')
    
    return render(request, 'tenants/rejected.html', {
        'reason': request.user.rejection_reason
    })


@login_required
def no_database_view(request):
    """Page shown to approved users without a database assigned."""
    if not request.user.is_approved:
        return redirect('tenants:pending_approval')
    
    if request.user.assigned_database:
        return redirect('erp:dashboard')
    
    return render(request, 'tenants/no_database.html')


@login_required
def profile_view(request):
    """User profile page."""
    return render(request, 'tenants/profile.html', {
        'user': request.user,
        'database': request.user.assigned_database
    })
