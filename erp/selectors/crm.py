"""
Selectors – CRM

Leads, Campaigns, Tasks.
"""

from django.db.models import Q

from erp.models import Lead, Campaign, Task

__all__ = [
    'get_lead_list',
    'get_lead_detail_context',
    'get_campaign_list',
    'get_campaign_detail_context',
    'get_task_list',
    'get_task_detail_context',
]


def get_lead_list(company, *, status=None, source=None, search=None):
    qs = Lead.objects.filter(company=company).order_by('-created_at')
    if status:
        qs = qs.filter(status=status)
    if source:
        qs = qs.filter(source=source)
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(lead_number__icontains=search)
        )
    return qs


def get_lead_detail_context(lead):
    return {
        'activities': lead.activities.order_by('-activity_date'),
        'quotes': lead.quotes.order_by('-quote_date'),
    }


def get_campaign_list(company, *, status=None, limit=100):
    qs = (
        Campaign.objects.filter(company=company)
        .select_related('owner', 'currency')
    )
    if status:
        qs = qs.filter(status=status)
    return qs.order_by('-start_date')[:limit]


def get_campaign_detail_context(campaign, limit=20):
    return {
        'leads': campaign.campaign_leads.select_related('lead')[:limit],
    }


def get_task_list(company, *, status=None, search=None):
    qs = Task.objects.filter(company=company).order_by('-created_at')
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
        )
    return qs


def get_task_detail_context(task):
    return {
        'comments': task.comments.select_related('user').order_by('-created_at'),
    }
