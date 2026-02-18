"""
ERP Admin – CRM models
"""

from django.contrib import admin
from erp.models import (
    Lead, LeadActivity, CustomerInteraction, Campaign, CampaignLead, Task, TaskComment,
)


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    ordering = ['-activity_date']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['lead_number', 'full_name', 'email', 'phone', 'source', 'status', 'assigned_to']
    list_filter = ['status', 'source', 'assigned_to']
    search_fields = ['lead_number', 'first_name', 'last_name', 'email', 'company_name']
    inlines = [LeadActivityInline]


@admin.register(CustomerInteraction)
class CustomerInteractionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'interaction_type', 'subject', 'interaction_date', 'handled_by']
    list_filter = ['interaction_type', 'interaction_date']
    search_fields = ['customer__name', 'subject']
    date_hierarchy = 'interaction_date'


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'campaign_type', 'status', 'start_date', 'budget', 'actual_leads']
    list_filter = ['status', 'campaign_type']
    search_fields = ['name']
    date_hierarchy = 'start_date'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'status', 'assigned_to', 'due_date']
    list_filter = ['status', 'priority', 'assigned_to']
    search_fields = ['title', 'description']
