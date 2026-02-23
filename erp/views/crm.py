"""
ERP Views – CRM

Leads, Campaigns, Tasks.
"""

from django.db.models import Q

from erp.models import Lead, Campaign, Task, Employee
from erp.forms import (
    LeadForm, LeadActivityForm,
    CampaignForm,
    TaskForm, TaskCommentForm,
)
from erp.services import get_lead_number
from ._common import (
    render, get_object_or_404, redirect, messages, reverse,
    get_user_company, staff_member_required,
)


# ── Leads ───────────────────────────────────────────────────────────────────

@staff_member_required
def lead_list(request):
    company = get_user_company(request.user)
    leads = Lead.objects.filter(company=company).order_by('-created_at')

    status = request.GET.get('status')
    if status:
        leads = leads.filter(status=status)

    source = request.GET.get('source')
    if source:
        leads = leads.filter(source=source)

    search = request.GET.get('search')
    if search:
        leads = leads.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(lead_number__icontains=search)
        )

    return render(request, 'erp/leads/list.html', {
        'leads': leads,
        'statuses': Lead.Status.choices,
        'sources': Lead.Source.choices,
    })


@staff_member_required
def lead_detail(request, pk):
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)
    from datetime import date

    return render(request, 'erp/leads/detail.html', {
        'lead': lead,
        'activities': lead.activities.order_by('-activity_date'),
        'quotes': lead.quotes.order_by('-quote_date'),
        'today': date.today(),
    })


@staff_member_required
def lead_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = LeadForm(request.POST, company=company)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.company = company
            lead.lead_number = get_lead_number(company)
            lead.save()
            messages.success(request, f'Lead "{lead.full_name}" created successfully.')
            return redirect('erp:lead_detail', pk=lead.pk)
    else:
        form = LeadForm(company=company)

    return render(request, 'erp/leads/form.html', {
        'form': form,
        'title': 'Add Lead',
        'submit_text': 'Create Lead',
    })


@staff_member_required
def lead_edit(request, pk):
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)

    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Lead "{lead.full_name}" updated successfully.')
            return redirect('erp:lead_detail', pk=lead.pk)
    else:
        form = LeadForm(instance=lead, company=company)

    return render(request, 'erp/leads/form.html', {
        'form': form,
        'lead': lead,
        'title': f'Edit Lead: {lead.full_name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def lead_delete(request, pk):
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)

    if request.method == 'POST':
        name = lead.full_name
        lead.delete()
        messages.success(request, f'Lead "{name}" deleted successfully.')
        return redirect('erp:lead_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': lead,
        'object_type': 'Lead',
        'cancel_url': reverse('erp:lead_detail', args=[pk]),
    })


@staff_member_required
def lead_add_activity(request, pk):
    company = get_user_company(request.user)
    lead = get_object_or_404(Lead, pk=pk, company=company)

    if request.method == 'POST':
        form = LeadActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.lead = lead
            # performed_by is FK to Employee, not User
            try:
                activity.performed_by = request.user.employee_profile
            except Employee.DoesNotExist:
                activity.performed_by = None
            activity.save()
            messages.success(request, 'Activity added successfully.')
            return redirect('erp:lead_detail', pk=lead.pk)
    else:
        form = LeadActivityForm()

    return render(request, 'erp/leads/activity_form.html', {
        'form': form,
        'lead': lead,
        'title': f'Add Activity for {lead.full_name}',
    })


# ── Campaigns ───────────────────────────────────────────────────────────────

@staff_member_required
def campaign_list(request):
    company = get_user_company(request.user)
    campaigns = Campaign.objects.filter(company=company).select_related('owner', 'currency')

    status = request.GET.get('status')
    if status:
        campaigns = campaigns.filter(status=status)

    return render(request, 'erp/campaigns/list.html', {
        'campaigns': campaigns.order_by('-start_date')[:100],
        'statuses': Campaign.Status.choices,
    })


@staff_member_required
def campaign_detail(request, pk):
    company = get_user_company(request.user)
    campaign = get_object_or_404(Campaign, pk=pk, company=company)

    return render(request, 'erp/campaigns/detail.html', {
        'campaign': campaign,
        'leads': campaign.campaign_leads.select_related('lead')[:20],
    })


@staff_member_required
def campaign_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = CampaignForm(request.POST, company=company)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.company = company
            campaign.save()
            messages.success(request, f'Campaign "{campaign.name}" created successfully.')
            return redirect('erp:campaign_detail', pk=campaign.pk)
    else:
        form = CampaignForm(company=company)

    return render(request, 'erp/campaigns/form.html', {
        'form': form,
        'title': 'Create Campaign',
        'submit_text': 'Create Campaign',
    })


@staff_member_required
def campaign_edit(request, pk):
    company = get_user_company(request.user)
    campaign = get_object_or_404(Campaign, pk=pk, company=company)

    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Campaign "{campaign.name}" updated successfully.')
            return redirect('erp:campaign_detail', pk=campaign.pk)
    else:
        form = CampaignForm(instance=campaign, company=company)

    return render(request, 'erp/campaigns/form.html', {
        'form': form,
        'campaign': campaign,
        'title': f'Edit Campaign: {campaign.name}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def campaign_delete(request, pk):
    company = get_user_company(request.user)
    campaign = get_object_or_404(Campaign, pk=pk, company=company)

    if request.method == 'POST':
        name = campaign.name
        campaign.delete()
        messages.success(request, f'Campaign "{name}" deleted successfully.')
        return redirect('erp:campaign_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': campaign,
        'object_type': 'Campaign',
        'cancel_url': reverse('erp:campaign_detail', args=[pk]),
    })


# ── Tasks ───────────────────────────────────────────────────────────────────

@staff_member_required
def task_list(request):
    company = get_user_company(request.user)
    tasks = Task.objects.filter(company=company).select_related('assigned_to').order_by('-created_at')

    status = request.GET.get('status')
    if status:
        tasks = tasks.filter(status=status)

    priority = request.GET.get('priority')
    if priority:
        tasks = tasks.filter(priority=priority)

    my_tasks = request.GET.get('my_tasks')
    if my_tasks and hasattr(request.user, 'employee_profile'):
        tasks = tasks.filter(assigned_to=request.user.employee_profile)

    return render(request, 'erp/tasks/list.html', {
        'tasks': tasks,
        'statuses': Task.Status.choices,
        'priorities': Task.Priority.choices,
    })


@staff_member_required
def task_detail(request, pk):
    company = get_user_company(request.user)
    task = get_object_or_404(Task, pk=pk, company=company)

    return render(request, 'erp/tasks/detail.html', {
        'task': task,
        'comments': task.comments.select_related('author').order_by('created_at'),
    })


@staff_member_required
def task_create(request):
    company = get_user_company(request.user)

    if request.method == 'POST':
        form = TaskForm(request.POST, company=company)
        if form.is_valid():
            task = form.save(commit=False)
            task.company = company
            task.created_by = request.user
            task.save()
            messages.success(request, f'Task "{task.title}" created successfully.')
            return redirect('erp:task_detail', pk=task.pk)
    else:
        form = TaskForm(company=company)

    return render(request, 'erp/tasks/form.html', {
        'form': form,
        'title': 'Add Task',
        'submit_text': 'Create Task',
    })


@staff_member_required
def task_edit(request, pk):
    company = get_user_company(request.user)
    task = get_object_or_404(Task, pk=pk, company=company)

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Task "{task.title}" updated successfully.')
            return redirect('erp:task_detail', pk=task.pk)
    else:
        form = TaskForm(instance=task, company=company)

    return render(request, 'erp/tasks/form.html', {
        'form': form,
        'task': task,
        'title': f'Edit Task: {task.title}',
        'submit_text': 'Save Changes',
    })


@staff_member_required
def task_delete(request, pk):
    company = get_user_company(request.user)
    task = get_object_or_404(Task, pk=pk, company=company)

    if request.method == 'POST':
        title = task.title
        task.delete()
        messages.success(request, f'Task "{title}" deleted successfully.')
        return redirect('erp:task_list')

    return render(request, 'erp/confirm_delete.html', {
        'object': task,
        'object_type': 'Task',
        'cancel_url': reverse('erp:task_detail', args=[pk]),
    })


@staff_member_required
def task_add_comment(request, pk):
    company = get_user_company(request.user)
    task = get_object_or_404(Task, pk=pk, company=company)

    if request.method == 'POST':
        form = TaskCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            messages.success(request, 'Comment added successfully.')
            return redirect('erp:task_detail', pk=task.pk)

    return redirect('erp:task_detail', pk=task.pk)
