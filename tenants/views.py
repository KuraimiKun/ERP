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


# ── Employee Self-Registration (public) ─────────────────────────────────────

@require_http_methods(["GET", "POST"])
def employee_register_view(request, token):
    """
    Public page where employees self-register using an invite link.

    Flow:
    1. Look up EmployeeInviteLink by token (default DB).
    2. On POST, create TenantUser (both DBs) + Employee (tenant DB)
       + inactive DatabaseAssignment.
    3. Employee waits for owner approval.
    """
    from .models import EmployeeInviteLink, DatabaseAssignment
    from .routers import add_tenant_database, set_current_db_alias, clear_current_db_alias
    from erp.forms.employee_registration import EmployeeRegistrationForm
    from erp.models import Employee, Company
    from django.utils import timezone as tz

    # Look up invite link in default DB
    try:
        invite = EmployeeInviteLink.objects.using('default').get(token=token)
    except EmployeeInviteLink.DoesNotExist:
        messages.error(request, 'Invalid or expired registration link.')
        return redirect('tenants:login')

    if not invite.is_valid:
        messages.error(request, 'This registration link is no longer valid.')
        return redirect('tenants:login')

    if request.method == 'POST':
        form = EmployeeRegistrationForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            # Check if email is already taken
            if TenantUser.objects.using('default').filter(
                email=cd['email']
            ).exists():
                form.add_error('email', 'This email is already registered.')
            else:
                tenant_db = invite.database
                db_alias = add_tenant_database(tenant_db)

                # 1. Create TenantUser in DEFAULT DB
                user = TenantUser(
                    email=cd['email'],
                    first_name=cd['first_name'],
                    last_name=cd['last_name'],
                    phone=cd.get('phone', ''),
                    company_name=invite.company_name,
                    is_approved=False,
                    approval_status='pending',
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                )
                user.set_password(cd['password1'])
                user.save(using='default')

                # 2. Create same user in TENANT DB (for FK relationships)
                tenant_user = TenantUser(
                    id=user.id,
                    email=user.email,
                    password=user.password,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    phone=user.phone,
                    company_name=invite.company_name,
                    is_approved=False,
                    approval_status='pending',
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                    date_joined=user.date_joined,
                )
                try:
                    tenant_user.save(using=db_alias, force_insert=True)
                except Exception:
                    # If user already exists in tenant DB, update it
                    TenantUser.objects.using(db_alias).filter(
                        id=user.id
                    ).update(
                        email=user.email,
                        password=user.password,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        is_approved=False,
                        approval_status='pending',
                    )

                # 3. Create Employee in TENANT DB
                set_current_db_alias(db_alias)
                try:
                    company = Company.objects.using(db_alias).first()
                    currency = company.base_currency if company else None

                    emp = Employee(
                        user_id=user.id,
                        employee_id=f'PENDING-{str(user.id)[:8]}',
                        first_name=cd['first_name'],
                        last_name=cd['last_name'],
                        first_name_ar=cd.get('first_name_ar', ''),
                        last_name_ar=cd.get('last_name_ar', ''),
                        gender=cd['gender'],
                        date_of_birth=cd['date_of_birth'],
                        nationality=cd.get('nationality', ''),
                        email=cd['email'],
                        phone=cd.get('phone', ''),
                        emergency_contact_name=cd.get('emergency_contact_name', ''),
                        emergency_contact_phone=cd.get('emergency_contact_phone', ''),
                        address=cd.get('address', ''),
                        city=cd.get('city', ''),
                        country=cd.get('country', ''),
                        national_id=cd.get('national_id', ''),
                        company=company,
                        job_title=cd.get('job_title', ''),
                        hire_date=tz.now().date(),
                        basic_salary=0,
                        currency=currency,
                        approval_status='pending',
                        registered_via=token,
                    )
                    emp.save(using=db_alias)
                finally:
                    clear_current_db_alias()

                # 4. Create inactive DatabaseAssignment (default DB)
                DatabaseAssignment.objects.using('default').create(
                    user=user,
                    database=tenant_db,
                    role='user',
                    is_active=False,
                )

                # 5. Update invite link counter
                invite.registration_count += 1
                invite.save(using='default', update_fields=['registration_count'])

                messages.success(
                    request,
                    'Registration submitted successfully! Please wait for '
                    'your employer to approve your account.',
                )
                return redirect('tenants:login')
    else:
        form = EmployeeRegistrationForm()

    return render(request, 'tenants/employee_register.html', {
        'form': form,
        'company_name': invite.company_name,
        'company_name_ar': invite.company_name_ar,
    })
