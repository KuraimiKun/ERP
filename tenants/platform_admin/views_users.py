"""
Platform Admin - User Management Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q, F
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from tenants.models import (
    TenantUser, PostgresServer, TenantDatabase,
    DatabaseAssignment, ServerLog,
)
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_user_list(request):
    """List all tenant users with filtering and search."""
    qs = TenantUser.objects.filter(is_staff=False).order_by('-created_at')

    # Filters
    status = request.GET.get('status')
    if status in ('pending', 'approved', 'rejected', 'suspended'):
        qs = qs.filter(approval_status=status)

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(company_name__icontains=search)
        )

    has_db = request.GET.get('has_db')
    if has_db == '1':
        qs = qs.filter(database_assignments__is_active=True).distinct()
    elif has_db == '0':
        qs = qs.exclude(database_assignments__is_active=True)

    page = paginate(request, qs)

    context = pa_context(request, {
        'users': page,
        'current_status': status,
        'search_query': search,
        'has_db_filter': has_db,
        'status_counts': {
            'all': TenantUser.objects.filter(is_staff=False).count(),
            'pending': TenantUser.objects.filter(approval_status='pending', is_staff=False).count(),
            'approved': TenantUser.objects.filter(approval_status='approved', is_staff=False).count(),
            'rejected': TenantUser.objects.filter(approval_status='rejected', is_staff=False).count(),
            'suspended': TenantUser.objects.filter(approval_status='suspended', is_staff=False).count(),
        },
    })
    return render(request, 'platform_admin/users/list.html', context)


@platform_admin_required
def pa_user_detail(request, pk):
    """Detailed view of a single user."""
    user_obj = get_object_or_404(TenantUser, pk=pk)
    assignments = DatabaseAssignment.objects.filter(user=user_obj).select_related('database', 'database__server')
    logs = ServerLog.objects.filter(user=user_obj).order_by('-created_at')[:20]

    context = pa_context(request, {
        'tenant_user': user_obj,
        'assignments': assignments,
        'logs': logs,
        'available_databases': TenantDatabase.objects.filter(status='active'),
    })
    return render(request, 'platform_admin/users/detail.html', context)


@platform_admin_required
@require_POST
def pa_user_approve(request, pk):
    """Approve a pending user and optionally create/assign a database."""
    user_obj = get_object_or_404(TenantUser, pk=pk)

    if user_obj.approval_status != 'pending':
        messages.warning(request, _('User is not in pending status.'))
        return redirect('tenants:pa_user_detail', pk=pk)

    db_action = request.POST.get('db_action', 'existing')
    db_id = request.POST.get('database_id')

    user_obj.approve(approved_by=request.user)

    if db_action == 'new':
        # Create a new database for this user
        server = PostgresServer.objects.filter(status='active').annotate(
            db_count=Count('databases')
        ).filter(db_count__lt=F('max_databases')).first()

        if server:
            try:
                from tenants.services import DatabaseService
                db_service = DatabaseService()
                db_name = f"erp_{user_obj.company_name.lower().replace(' ', '_')[:20]}_{str(user_obj.pk)[:8]}"
                tenant_db = db_service.create_tenant_database(
                    server=server,
                    name=db_name,
                    display_name=user_obj.company_name or user_obj.email,
                    created_by=request.user,
                )
                DatabaseAssignment.objects.create(
                    user=user_obj,
                    database=tenant_db,
                    role='owner',
                    assigned_by=request.user,
                )
                messages.success(request, _('User approved and new database created.'))
            except Exception as e:
                messages.error(request, _(f'User approved but database creation failed: {e}'))
        else:
            messages.warning(request, _('User approved but no available server found for new database.'))

    elif db_action == 'existing' and db_id:
        try:
            tenant_db = TenantDatabase.objects.get(pk=db_id, status='active')
            DatabaseAssignment.objects.create(
                user=user_obj,
                database=tenant_db,
                role=request.POST.get('role', 'owner'),
                assigned_by=request.user,
            )
            # Sync user to tenant DB
            try:
                from tenants.services import DatabaseService
                from tenants.routers import add_tenant_database
                db_alias = add_tenant_database(tenant_db)
                from tenants.services.database_service import sync_user_to_tenant_db
                sync_user_to_tenant_db(user_obj, db_alias)
            except Exception:
                pass
            messages.success(request, _('User approved and assigned to existing database.'))
        except TenantDatabase.DoesNotExist:
            messages.warning(request, _('User approved but selected database not found.'))
    else:
        messages.success(request, _('User approved successfully.'))

    return redirect('tenants:pa_user_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_user_reject(request, pk):
    """Reject a pending user."""
    user_obj = get_object_or_404(TenantUser, pk=pk)
    reason = request.POST.get('reason', '')
    user_obj.reject(reason=reason)
    messages.success(request, _('User has been rejected.'))
    return redirect('tenants:pa_user_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_user_suspend(request, pk):
    """Suspend an approved user."""
    user_obj = get_object_or_404(TenantUser, pk=pk)
    user_obj.suspend()
    messages.success(request, _('User has been suspended.'))
    return redirect('tenants:pa_user_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_user_reactivate(request, pk):
    """Reactivate a suspended or rejected user."""
    user_obj = get_object_or_404(TenantUser, pk=pk)
    user_obj.is_approved = True
    user_obj.approval_status = 'approved'
    user_obj.is_active = True
    user_obj.save()
    messages.success(request, _('User has been reactivated.'))
    return redirect('tenants:pa_user_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_user_delete(request, pk):
    """Delete a user permanently."""
    user_obj = get_object_or_404(TenantUser, pk=pk)
    email = user_obj.email
    user_obj.delete()
    messages.success(request, _(f'User {email} has been permanently deleted.'))
    return redirect('tenants:pa_user_list')


@platform_admin_required
@require_POST
def pa_user_assign_db(request, pk):
    """Assign a database to a user."""
    user_obj = get_object_or_404(TenantUser, pk=pk)
    db_id = request.POST.get('database_id')
    role = request.POST.get('role', 'user')

    try:
        tenant_db = get_object_or_404(TenantDatabase, pk=db_id, status='active')

        # Deactivate existing assignments
        if request.POST.get('deactivate_existing') == '1':
            DatabaseAssignment.objects.filter(
                user=user_obj, is_active=True
            ).update(is_active=False, deactivated_at=timezone.now())

        DatabaseAssignment.objects.create(
            user=user_obj,
            database=tenant_db,
            role=role,
            assigned_by=request.user,
        )

        # Sync user to tenant DB
        try:
            from tenants.services.database_service import sync_user_to_tenant_db
            from tenants.routers import add_tenant_database
            db_alias = add_tenant_database(tenant_db)
            sync_user_to_tenant_db(user_obj, db_alias)
        except Exception:
            pass

        messages.success(request, _('Database assigned successfully.'))
    except Exception as e:
        messages.error(request, _(f'Failed to assign database: {e}'))

    return redirect('tenants:pa_user_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_bulk_user_action(request):
    """Handle bulk user actions via AJAX."""
    action = request.POST.get('action')
    user_ids = request.POST.getlist('user_ids')

    if not user_ids:
        return JsonResponse({'error': 'No users selected.'}, status=400)

    users = TenantUser.objects.filter(pk__in=user_ids, is_staff=False)
    count = users.count()

    if action == 'approve':
        for u in users.filter(approval_status='pending'):
            u.approve(approved_by=request.user)
        return JsonResponse({'success': True, 'message': f'{count} user(s) approved.'})
    elif action == 'reject':
        reason = request.POST.get('reason', 'Bulk rejection')
        for u in users.filter(approval_status='pending'):
            u.reject(reason=reason)
        return JsonResponse({'success': True, 'message': f'{count} user(s) rejected.'})
    elif action == 'suspend':
        for u in users.filter(approval_status='approved'):
            u.suspend()
        return JsonResponse({'success': True, 'message': f'{count} user(s) suspended.'})
    elif action == 'delete':
        users.delete()
        return JsonResponse({'success': True, 'message': f'{count} user(s) deleted.'})

    return JsonResponse({'error': 'Invalid action.'}, status=400)
