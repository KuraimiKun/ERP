"""
Tenant-Side Support Ticket Views

Views for tenant users to create, view, and reply to support tickets.
These views are accessible to any authenticated, approved user.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count

from tenants.models import (
    Ticket, TicketMessage, TicketAttachment, TicketCategory,
    Announcement,
)
from tenants.platform_admin.forms import (
    TenantTicketForm, TenantTicketReplyForm, TicketRatingForm,
)


def _tenant_context(request, extra=None):
    """Common context for tenant support pages."""
    ctx = {
        'open_ticket_count': Ticket.objects.filter(
            created_by=request.user,
        ).exclude(status__in=['resolved', 'closed']).count(),
        # Active announcements for the tenant
        'announcements': Announcement.objects.filter(
            is_active=True,
            audience__in=['all', 'tenants'],
        ).exclude(
            dismissals__user=request.user,
        ).order_by('-is_pinned', '-created_at')[:3],
    }
    if extra:
        ctx.update(extra)
    return ctx


@login_required
def tenant_ticket_list(request):
    """List the current user's tickets."""
    qs = Ticket.objects.filter(
        created_by=request.user,
    ).select_related('category', 'assigned_to').annotate(
        msg_count=Count('messages'),
    )

    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)

    # Stats for the user's tickets
    user_tickets = Ticket.objects.filter(created_by=request.user)
    stats = {
        'open': user_tickets.filter(status='open').count(),
        'in_progress': user_tickets.filter(status='in_progress').count(),
        'waiting': user_tickets.filter(status='waiting_customer').count(),
        'resolved': user_tickets.filter(status='resolved').count(),
    }

    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))

    context = _tenant_context(request, {
        'page': page,
        'current_status': status,
        'statuses': Ticket.STATUS_CHOICES,
        'stats': stats,
    })
    return render(request, 'tenants/tickets/list.html', context)


@login_required
def tenant_ticket_create(request):
    """Create a new support ticket."""
    if request.method == 'POST':
        form = TenantTicketForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            ticket.save()

            # Initial description becomes first message
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                body=ticket.description,
            )

            # Handle attachment
            if request.FILES.get('attachment'):
                f = request.FILES['attachment']
                TicketAttachment.objects.create(
                    ticket=ticket,
                    uploaded_by=request.user,
                    file=f,
                    original_filename=f.name,
                    file_size=f.size,
                )

            messages.success(
                request,
                _('Ticket %(num)s created successfully. We will get back to you shortly.')
                % {'num': ticket.ticket_number},
            )
            return redirect('tenants:tenant_ticket_detail', pk=ticket.pk)
    else:
        form = TenantTicketForm()

    context = _tenant_context(request, {
        'form': form,
        'categories': TicketCategory.objects.filter(is_active=True),
    })
    return render(request, 'tenants/tickets/create.html', context)


@login_required
def tenant_ticket_detail(request, pk):
    """View a ticket and its conversation."""
    ticket = get_object_or_404(
        Ticket.objects.select_related('category', 'assigned_to'),
        pk=pk,
        created_by=request.user,
    )
    # Filter out internal notes (not visible to tenant)
    conversation = ticket.messages.filter(
        is_internal_note=False,
    ).select_related('sender').order_by('created_at')
    attachments = ticket.attachments.select_related('uploaded_by')

    reply_form = TenantTicketReplyForm()
    rating_form = TicketRatingForm()

    context = _tenant_context(request, {
        'ticket': ticket,
        'conversation': conversation,
        'attachments': attachments,
        'reply_form': reply_form,
        'rating_form': rating_form,
    })
    return render(request, 'tenants/tickets/detail.html', context)


@login_required
@require_POST
def tenant_ticket_reply(request, pk):
    """Tenant user replies to their ticket."""
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)

    if ticket.status == 'closed':
        messages.error(request, _('This ticket is closed and cannot receive replies.'))
        return redirect('tenants:tenant_ticket_detail', pk=pk)

    form = TenantTicketReplyForm(request.POST, request.FILES)
    if form.is_valid():
        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            body=form.cleaned_data['body'],
        )
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
        # Change status to waiting on admin
        ticket.status = 'waiting_admin'
        ticket.save(update_fields=['status', 'updated_at'])
        messages.success(request, _('Reply sent.'))
    else:
        messages.error(request, _('Please enter a message.'))

    return redirect('tenants:tenant_ticket_detail', pk=pk)


@login_required
@require_POST
def tenant_ticket_close(request, pk):
    """Tenant user closes their own ticket."""
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)
    ticket.status = 'closed'
    ticket.closed_at = timezone.now()
    if not ticket.resolved_at:
        ticket.resolved_at = timezone.now()
    ticket.save(update_fields=['status', 'closed_at', 'resolved_at', 'updated_at'])
    messages.success(request, _('Ticket closed. Thank you!'))
    return redirect('tenants:tenant_ticket_detail', pk=pk)


@login_required
@require_POST
def tenant_ticket_rate(request, pk):
    """Tenant user rates a resolved/closed ticket."""
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)
    form = TicketRatingForm(request.POST)

    if form.is_valid() and ticket.status in ('resolved', 'closed'):
        ticket.satisfaction_rating = form.cleaned_data['satisfaction_rating']
        ticket.satisfaction_feedback = form.cleaned_data.get('satisfaction_feedback', '')
        ticket.save(update_fields=['satisfaction_rating', 'satisfaction_feedback'])
        messages.success(request, _('Thank you for your feedback!'))
    else:
        messages.error(request, _('Rating could not be saved.'))

    return redirect('tenants:tenant_ticket_detail', pk=pk)


@login_required
@require_POST
def tenant_ticket_reopen(request, pk):
    """Tenant user reopens a resolved ticket."""
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)
    if ticket.status in ('resolved', 'closed'):
        ticket.status = 'open'
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.save(update_fields=['status', 'resolved_at', 'closed_at', 'updated_at'])
        messages.info(request, _('Ticket reopened.'))
    return redirect('tenants:tenant_ticket_detail', pk=pk)
