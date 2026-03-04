"""
Platform Admin - Support Ticket Views

Admin-side views for managing support tickets from tenant users.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Count, Avg
from django.views.decorators.http import require_POST

from tenants.models import (
    Ticket, TicketMessage, TicketAttachment, TicketCategory, TenantUser,
)
from .forms import TicketCategoryForm, AdminTicketReplyForm, TicketAssignForm
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_ticket_list(request):
    """List all tickets with filters."""
    qs = Ticket.objects.select_related(
        'created_by', 'assigned_to', 'category',
    ).annotate(
        msg_count=Count('messages'),
    )

    # Filters
    status = request.GET.get('status')
    priority = request.GET.get('priority')
    assigned = request.GET.get('assigned')
    q = request.GET.get('q', '').strip()

    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if assigned == 'me':
        qs = qs.filter(assigned_to=request.user)
    elif assigned == 'unassigned':
        qs = qs.filter(assigned_to__isnull=True)
    if q:
        qs = qs.filter(
            Q(ticket_number__icontains=q) |
            Q(subject__icontains=q) |
            Q(created_by__email__icontains=q) |
            Q(created_by__company_name__icontains=q)
        )

    # Stats
    all_count = Ticket.objects.count()
    open_count = Ticket.objects.filter(status='open').count()
    progress_count = Ticket.objects.filter(status='in_progress').count()
    waiting_count = Ticket.objects.filter(
        status__in=['waiting_customer', 'waiting_admin']
    ).count()
    resolved_count = Ticket.objects.filter(status='resolved').count()
    my_count = Ticket.objects.filter(assigned_to=request.user).exclude(
        status__in=['resolved', 'closed']
    ).count()

    page = paginate(request, qs, per_page=20)
    admins = TenantUser.objects.filter(is_superuser=True)

    context = pa_context(request, {
        'page': page,
        'current_status': status,
        'current_priority': priority,
        'current_assigned': assigned,
        'q': q,
        'all_count': all_count,
        'open_count': open_count,
        'progress_count': progress_count,
        'waiting_count': waiting_count,
        'resolved_count': resolved_count,
        'my_count': my_count,
        'admins': admins,
        'statuses': Ticket.STATUS_CHOICES,
        'priorities': Ticket.PRIORITY_CHOICES,
    })
    return render(request, 'platform_admin/tickets/list.html', context)


@platform_admin_required
def pa_ticket_detail(request, pk):
    """View ticket detail with conversation thread."""
    ticket = get_object_or_404(
        Ticket.objects.select_related('created_by', 'assigned_to', 'category'),
        pk=pk,
    )
    messages_qs = ticket.messages.select_related('sender').order_by('created_at')
    attachments = ticket.attachments.select_related('uploaded_by')
    admins = TenantUser.objects.filter(is_superuser=True)

    reply_form = AdminTicketReplyForm()
    assign_form = TicketAssignForm()
    assign_form.fields['assigned_to'].queryset = admins

    context = pa_context(request, {
        'ticket': ticket,
        'conversation': messages_qs,
        'attachments': attachments,
        'reply_form': reply_form,
        'assign_form': assign_form,
        'admins': admins,
    })
    return render(request, 'platform_admin/tickets/detail.html', context)


@platform_admin_required
@require_POST
def pa_ticket_reply(request, pk):
    """Admin replies to a ticket."""
    ticket = get_object_or_404(Ticket, pk=pk)
    form = AdminTicketReplyForm(request.POST, request.FILES)

    if form.is_valid():
        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            body=form.cleaned_data['body'],
            is_internal_note=form.cleaned_data.get('is_internal_note', False),
        )
        # Handle file attachment
        if request.FILES.get('attachment'):
            f = request.FILES['attachment']
            TicketAttachment.objects.create(
                ticket=ticket,
                message=msg,
                uploaded_by=request.user,
                file=f,
                original_filename=f.name,
                file_size=f.size,
            )

        # Update ticket status
        if not form.cleaned_data.get('is_internal_note'):
            ticket.status = 'waiting_customer'
            ticket.save(update_fields=['status', 'updated_at'])

        messages.success(request, _('Reply sent successfully.'))
    else:
        messages.error(request, _('Please enter a message.'))

    return redirect('tenants:pa_ticket_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_ticket_assign(request, pk):
    """Assign a ticket to an admin."""
    ticket = get_object_or_404(Ticket, pk=pk)
    admin_pk = request.POST.get('assigned_to')

    if admin_pk:
        try:
            admin_user = TenantUser.objects.get(pk=admin_pk, is_superuser=True)
            ticket.assigned_to = admin_user
            if ticket.status == 'open':
                ticket.status = 'in_progress'
            ticket.save(update_fields=['assigned_to', 'status', 'updated_at'])
            messages.success(
                request,
                _('Ticket assigned to %(name)s.') % {
                    'name': admin_user.get_full_name() or admin_user.email
                },
            )
        except TenantUser.DoesNotExist:
            messages.error(request, _('Invalid admin user.'))
    else:
        ticket.assigned_to = None
        ticket.save(update_fields=['assigned_to', 'updated_at'])
        messages.info(request, _('Ticket unassigned.'))

    return redirect('tenants:pa_ticket_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_ticket_status(request, pk):
    """Change ticket status."""
    ticket = get_object_or_404(Ticket, pk=pk)
    new_status = request.POST.get('status')

    valid_statuses = dict(Ticket.STATUS_CHOICES)
    if new_status in valid_statuses:
        old_status = ticket.status
        ticket.status = new_status

        if new_status == 'resolved' and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        elif new_status == 'closed' and not ticket.closed_at:
            ticket.closed_at = timezone.now()

        ticket.save(update_fields=['status', 'resolved_at', 'closed_at', 'updated_at'])

        # Auto-add a system message
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            body=f'Status changed from {dict(Ticket.STATUS_CHOICES).get(old_status)} to {valid_statuses[new_status]}.',
            is_internal_note=True,
        )
        messages.success(request, _('Status updated to %(s)s.') % {'s': valid_statuses[new_status]})
    else:
        messages.error(request, _('Invalid status.'))

    return redirect('tenants:pa_ticket_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_ticket_priority(request, pk):
    """Change ticket priority."""
    ticket = get_object_or_404(Ticket, pk=pk)
    new_priority = request.POST.get('priority')

    valid_priorities = dict(Ticket.PRIORITY_CHOICES)
    if new_priority in valid_priorities:
        ticket.priority = new_priority
        ticket.save(update_fields=['priority', 'updated_at'])
        messages.success(request, _('Priority updated.'))
    else:
        messages.error(request, _('Invalid priority.'))

    return redirect('tenants:pa_ticket_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_ticket_escalate(request, pk):
    """Toggle ticket escalation."""
    ticket = get_object_or_404(Ticket, pk=pk)
    ticket.is_escalated = not ticket.is_escalated
    ticket.save(update_fields=['is_escalated', 'updated_at'])
    if ticket.is_escalated:
        messages.warning(request, _('Ticket escalated.'))
    else:
        messages.info(request, _('Escalation removed.'))
    return redirect('tenants:pa_ticket_detail', pk=pk)


@platform_admin_required
@require_POST
def pa_ticket_close(request, pk):
    """Close a ticket."""
    ticket = get_object_or_404(Ticket, pk=pk)
    ticket.status = 'closed'
    ticket.closed_at = timezone.now()
    if not ticket.resolved_at:
        ticket.resolved_at = timezone.now()
    ticket.save(update_fields=['status', 'closed_at', 'resolved_at', 'updated_at'])
    messages.success(request, _('Ticket closed.'))
    return redirect('tenants:pa_ticket_detail', pk=pk)


# ── Categories CRUD ─────────────────────────────────────────────────────────

@platform_admin_required
def pa_ticket_categories(request):
    """Manage ticket categories."""
    categories = TicketCategory.objects.annotate(
        ticket_count=Count('tickets'),
    )
    form = TicketCategoryForm()

    if request.method == 'POST':
        form = TicketCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _('Category created.'))
            return redirect('tenants:pa_ticket_categories')

    context = pa_context(request, {
        'categories': categories,
        'form': form,
    })
    return render(request, 'platform_admin/tickets/categories.html', context)


@platform_admin_required
@require_POST
def pa_ticket_category_delete(request, pk):
    """Delete a ticket category."""
    cat = get_object_or_404(TicketCategory, pk=pk)
    cat.delete()
    messages.success(request, _('Category deleted.'))
    return redirect('tenants:pa_ticket_categories')


# ── Dashboard Stats API ─────────────────────────────────────────────────────

@platform_admin_required
def pa_ticket_stats_api(request):
    """JSON endpoint for ticket stats (live badge updates)."""
    from django.db.models.functions import TruncDate
    data = {
        'open': Ticket.objects.filter(status='open').count(),
        'in_progress': Ticket.objects.filter(status='in_progress').count(),
        'waiting_admin': Ticket.objects.filter(status='waiting_admin').count(),
        'my_assigned': Ticket.objects.filter(
            assigned_to=request.user,
        ).exclude(status__in=['resolved', 'closed']).count(),
        'avg_rating': Ticket.objects.filter(
            satisfaction_rating__isnull=False,
        ).aggregate(avg=Avg('satisfaction_rating'))['avg'] or 0,
    }
    return JsonResponse(data)
