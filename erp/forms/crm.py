"""
ERP Forms - CRM

Forms for Lead, LeadActivity, CustomerInteraction, Campaign, Task, TaskComment.
"""
from django import forms

from erp.models import Lead, LeadActivity, CustomerInteraction, Campaign, Task, TaskComment
from .mixins import BootstrapFormMixin, CompanyFilterMixin


class LeadForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Lead model."""

    class Meta:
        model = Lead
        fields = [
            'title', 'first_name', 'last_name', 'email', 'phone', 'mobile',
            'company_name', 'job_title', 'address', 'city', 'country',
            'source', 'status', 'service_interest',
            'estimated_value', 'expected_close_date', 'probability',
            'assigned_to', 'notes'
        ]
        widgets = {
            'expected_close_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class LeadActivityForm(BootstrapFormMixin, forms.ModelForm):
    """Form for LeadActivity model."""

    class Meta:
        model = LeadActivity
        fields = ['activity_type', 'subject', 'description', 'activity_date', 'is_completed']
        widgets = {
            'activity_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class CustomerInteractionForm(BootstrapFormMixin, forms.ModelForm):
    """Form for CustomerInteraction model."""

    class Meta:
        model = CustomerInteraction
        fields = [
            'interaction_type', 'subject', 'description', 'interaction_date',
            'requires_follow_up', 'follow_up_date', 'follow_up_notes'
        ]
        widgets = {
            'interaction_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'follow_up_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'follow_up_notes': forms.Textarea(attrs={'rows': 2}),
        }


class CampaignForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Campaign model."""

    class Meta:
        model = Campaign
        fields = [
            'name', 'campaign_type', 'status', 'start_date', 'end_date',
            'target_audience', 'currency', 'budget', 'expected_leads',
            'expected_revenue', 'description', 'owner'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'target_audience': forms.Textarea(attrs={'rows': 2}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class TaskForm(BootstrapFormMixin, CompanyFilterMixin, forms.ModelForm):
    """Form for Task model."""

    class Meta:
        model = Task
        fields = [
            'title', 'description', 'priority', 'status',
            'assigned_to', 'due_date', 'related_customer', 'related_lead',
            'reminder_date'
        ]
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'reminder_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class TaskCommentForm(BootstrapFormMixin, forms.ModelForm):
    """Form for TaskComment model."""

    class Meta:
        model = TaskComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Add a comment...'}),
        }
