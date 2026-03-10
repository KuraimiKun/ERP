"""
Platform Admin - Invite Link Management Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST, require_http_methods
from datetime import timedelta

from tenants.models import (
    TenantDatabase, EmployeeInviteLink,
)
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_invite_list(request):
    """List all employee invite links."""
    qs = EmployeeInviteLink.objects.select_related(
        'database', 'database__server', 'created_by'
    ).order_by('-created_at')

    # Filters
    status = request.GET.get('status')
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)
    elif status == 'expired':
        qs = qs.filter(expires_at__lt=timezone.now())

    db_id = request.GET.get('database')
    if db_id:
        qs = qs.filter(database_id=db_id)

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(company_name__icontains=search)

    page = paginate(request, qs, per_page=25)

    context = pa_context(request, {
        'invite_links': page,
        'current_status': status,
        'search_query': search,
        'databases': TenantDatabase.objects.filter(status='active'),
        'total_links': EmployeeInviteLink.objects.count(),
        'active_links': EmployeeInviteLink.objects.filter(is_active=True).count(),
        'total_registrations': sum(
            EmployeeInviteLink.objects.values_list('registration_count', flat=True)
        ),
    })
    return render(request, 'platform_admin/invites/list.html', context)


@platform_admin_required
def pa_invite_detail(request, pk):
    """Detailed view of an invite link."""
    invite = get_object_or_404(
        EmployeeInviteLink.objects.select_related('database', 'database__server', 'created_by'),
        pk=pk
    )

    context = pa_context(request, {
        'invite': invite,
    })
    return render(request, 'platform_admin/invites/detail.html', context)


@platform_admin_required
@require_http_methods(['GET', 'POST'])
def pa_invite_create(request):
    """Create a new employee invite link."""
    if request.method == 'POST':
        db_id = request.POST.get('database_id')
        company_name = request.POST.get('company_name', '').strip()
        company_name_ar = request.POST.get('company_name_ar', '').strip()
        max_registrations = int(request.POST.get('max_registrations', 0))
        expires_days = int(request.POST.get('expires_days', 0))

        try:
            database = get_object_or_404(TenantDatabase, pk=db_id, status='active')

            invite = EmployeeInviteLink(
                database=database,
                created_by=request.user,
                company_name=company_name,
                company_name_ar=company_name_ar,
                max_registrations=max_registrations,
            )
            if expires_days > 0:
                invite.expires_at = timezone.now() + timedelta(days=expires_days)

            invite.save()

            messages.success(request, _('Invite link created successfully.'))
            return redirect('tenants:pa_invite_detail', pk=invite.pk)
        except Exception as e:
            messages.error(request, _(f'Failed to create invite link: {e}'))

    databases = TenantDatabase.objects.filter(status='active').select_related('server')
    context = pa_context(request, {
        'databases': databases,
    })
    return render(request, 'platform_admin/invites/create.html', context)


@platform_admin_required
@require_POST
def pa_invite_toggle(request, pk):
    """Activate or deactivate an invite link."""
    invite = get_object_or_404(EmployeeInviteLink, pk=pk)
    invite.is_active = not invite.is_active
    invite.save()

    status_text = _('activated') if invite.is_active else _('deactivated')
    messages.success(request, _(f'Invite link {status_text}.'))
    return redirect('tenants:pa_invite_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_invite_delete(request, pk):
    """Delete an invite link permanently."""
    invite = get_object_or_404(EmployeeInviteLink, pk=pk)
    invite.delete()
    messages.success(request, _('Invite link has been deleted.'))
    return redirect('tenants:pa_invite_list')


@platform_admin_required
@require_POST
def pa_invite_reset_count(request, pk):
    """Reset the registration count for an invite link."""
    invite = get_object_or_404(EmployeeInviteLink, pk=pk)
    invite.registration_count = 0
    invite.save()
    messages.success(request, _('Registration count has been reset.'))
    return redirect('tenants:pa_invite_detail', pk=pk)
