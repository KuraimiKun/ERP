"""
ERP Views – Support Tickets

Tenant-user-facing views for creating, viewing, and replying to support
tickets from within the ERP dashboard.  All views use the standard
``@staff_member_required`` decorator and the ``erp/`` template namespace.
"""

from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Count

from tenants.models import (
    Ticket, TicketMessage, TicketAttachment,
)
from tenants.platform_admin.forms import (
    TenantTicketForm, TenantTicketReplyForm, TicketRatingForm,
)
from ._common import (
    render, get_object_or_404, redirect, messages, paginate_qs,
    staff_member_required,
)


# ── List ────────────────────────────────────────────────────────────────────

@staff_member_required
def support_ticket_list(request):
    """List the current user's support tickets."""
    qs = Ticket.objects.filter(
        created_by=request.user,
    ).select_related('category', 'assigned_to').annotate(
        msg_count=Count('messages'),
    )

    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)

    user_tickets = Ticket.objects.filter(created_by=request.user)
    stats = {
        'open': user_tickets.filter(status='open').count(),
        'in_progress': user_tickets.filter(status='in_progress').count(),
        'waiting': user_tickets.filter(status='waiting_customer').count(),
        'resolved': user_tickets.filter(status='resolved').count(),
    }

    page_obj, query_string = paginate_qs(request, qs, per_page=15)

    return render(request, 'erp/support/list.html', {
        'page_obj': page_obj,
        'query_string': query_string,
        'current_status': status or '',
        'statuses': Ticket.STATUS_CHOICES,
        'stats': stats,
    })


# ── Create ──────────────────────────────────────────────────────────────────

@staff_member_required
def support_ticket_create(request):
    """Create a new support ticket."""
    if request.method == 'POST':
        form = TenantTicketForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            ticket.save()

            # First message from description
            TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                body=ticket.description,
            )

            # Attachment
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
                _('Ticket %(num)s created. We will get back to you shortly.')
                % {'num': ticket.ticket_number},
            )
            return redirect('erp:support_ticket_detail', pk=ticket.pk)
    else:
        form = TenantTicketForm()

    return render(request, 'erp/support/create.html', {
        'form': form,
    })


# ── Detail ──────────────────────────────────────────────────────────────────

@staff_member_required
def support_ticket_detail(request, pk):
    """Ticket detail page with conversation thread."""
    ticket = get_object_or_404(
        Ticket.objects.select_related('category', 'assigned_to'),
        pk=pk,
        created_by=request.user,
    )
    conversation = ticket.messages.filter(
        is_internal_note=False,
    ).select_related('sender').order_by('created_at')
    attachments = ticket.attachments.select_related('uploaded_by')

    return render(request, 'erp/support/detail.html', {
        'ticket': ticket,
        'conversation': conversation,
        'attachments': attachments,
        'reply_form': TenantTicketReplyForm(),
        'rating_form': TicketRatingForm(),
    })


# ── Reply ───────────────────────────────────────────────────────────────────

@staff_member_required
@require_POST
def support_ticket_reply(request, pk):
    """Reply to an existing ticket."""
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)

    if ticket.status == 'closed':
        messages.error(request, _('This ticket is closed.'))
        return redirect('erp:support_ticket_detail', pk=pk)

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
                ticket=ticket, message=msg,
                uploaded_by=request.user,
                file=f, original_filename=f.name, file_size=f.size,
            )
        ticket.status = 'waiting_admin'
        ticket.save(update_fields=['status', 'updated_at'])
        messages.success(request, _('Reply sent.'))
    else:
        messages.error(request, _('Please enter a message.'))

    return redirect('erp:support_ticket_detail', pk=pk)


# ── Close ───────────────────────────────────────────────────────────────────

@staff_member_required
@require_POST
def support_ticket_close(request, pk):
    """Close own ticket."""
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)
    ticket.status = 'closed'
    ticket.closed_at = timezone.now()
    if not ticket.resolved_at:
        ticket.resolved_at = timezone.now()
    ticket.save(update_fields=['status', 'closed_at', 'resolved_at', 'updated_at'])
    messages.success(request, _('Ticket closed. Thank you!'))
    return redirect('erp:support_ticket_detail', pk=pk)


# ── Rate ────────────────────────────────────────────────────────────────────

@staff_member_required
@require_POST
def support_ticket_rate(request, pk):
    """Rate a resolved / closed ticket."""
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)
    form = TicketRatingForm(request.POST)
    if form.is_valid() and ticket.status in ('resolved', 'closed'):
        ticket.satisfaction_rating = form.cleaned_data['satisfaction_rating']
        ticket.satisfaction_feedback = form.cleaned_data.get('satisfaction_feedback', '')
        ticket.save(update_fields=['satisfaction_rating', 'satisfaction_feedback'])
        messages.success(request, _('Thank you for your feedback!'))
    else:
        messages.error(request, _('Rating could not be saved.'))
    return redirect('erp:support_ticket_detail', pk=pk)


# ── Reopen ──────────────────────────────────────────────────────────────────

@staff_member_required
@require_POST
def support_ticket_reopen(request, pk):
    """Reopen a resolved / closed ticket."""
    ticket = get_object_or_404(Ticket, pk=pk, created_by=request.user)
    if ticket.status in ('resolved', 'closed'):
        ticket.status = 'open'
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.save(update_fields=['status', 'resolved_at', 'closed_at', 'updated_at'])
        messages.info(request, _('Ticket reopened.'))
    return redirect('erp:support_ticket_detail', pk=pk)
