"""
CRM (Customer Relationship Management) models for the ERP system.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .base import ERPBaseModel, TimeStampedModel


class Lead(ERPBaseModel):
    """Sales leads/prospects."""
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        CONTACTED = 'contacted', 'Contacted'
        QUALIFIED = 'qualified', 'Qualified'
        PROPOSAL = 'proposal', 'Proposal Sent'
        NEGOTIATION = 'negotiation', 'Negotiation'
        WON = 'won', 'Won'
        LOST = 'lost', 'Lost'
        INACTIVE = 'inactive', 'Inactive'

    class Source(models.TextChoices):
        WEBSITE = 'website', 'Website'
        REFERRAL = 'referral', 'Referral'
        SOCIAL = 'social', 'Social Media'
        ADVERTISEMENT = 'advertisement', 'Advertisement'
        EXHIBITION = 'exhibition', 'Exhibition/Event'
        COLD_CALL = 'cold_call', 'Cold Call'
        WALK_IN = 'walk_in', 'Walk-in'
        EMAIL = 'email', 'Email Campaign'
        OTHER = 'other', 'Other'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='leads'
    )
    
    # Lead Info
    lead_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    source = models.CharField(max_length=20, choices=Source.choices, blank=True)
    
    # Contact Information
    title = models.CharField(max_length=20, blank=True)  # Mr., Mrs., etc.
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    
    # Company (if B2B)
    company_name = models.CharField(max_length=255, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    
    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Opportunity
    service_interest = models.CharField(max_length=255, blank=True, help_text=_('Service the lead is interested in'))
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_close_date = models.DateField(null=True, blank=True)
    probability = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('Probability of conversion (0-100%)')
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads'
    )
    
    # Conversion
    converted_customer = models.ForeignKey(
        'erp.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_origin'
    )
    conversion_date = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    last_contact_date = models.DateTimeField(null=True, blank=True)
    next_follow_up = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name=_('Lead')
        verbose_name_plural = 'Leads'
        ordering = ['-created_at']
        unique_together = [('company', 'lead_number')]
        indexes = [
            models.Index(fields=['company', 'status'], name='idx_lead_company_status'),
            models.Index(fields=['company', 'assigned_to'], name='idx_lead_company_assigned'),
            models.Index(fields=['company', 'source'], name='idx_lead_company_source'),
            models.Index(fields=['status', 'next_follow_up'], name='idx_lead_status_followup'),
            # Rep workload view: filter by assigned_to + status + next_follow_up
            models.Index(fields=['assigned_to', 'status', 'next_follow_up'], name='idx_lead_rep_workload'),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.lead_number})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class LeadActivity(TimeStampedModel):
    """Activities/interactions for leads."""
    class ActivityType(models.TextChoices):
        CALL = 'call', 'Phone Call'
        EMAIL = 'email', 'Email'
        MEETING = 'meeting', 'Meeting'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        SMS = 'sms', 'SMS'
        NOTE = 'note', 'Note'
        TASK = 'task', 'Task'

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    activity_date = models.DateTimeField()
    
    # For scheduled activities
    is_completed = models.BooleanField(default=False)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    performed_by = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_activities'
    )

    class Meta:
        verbose_name=_('Lead Activity')
        verbose_name_plural = 'Lead Activities'
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['lead', 'activity_date'], name='idx_la_lead_date'),
        ]

    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.subject}"


class CustomerInteraction(TimeStampedModel):
    """Track all interactions with customers."""
    class InteractionType(models.TextChoices):
        CALL = 'call', 'Phone Call'
        EMAIL = 'email', 'Email'
        MEETING = 'meeting', 'Meeting'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        SMS = 'sms', 'SMS'
        SUPPORT = 'support', 'Support Request'
        COMPLAINT = 'complaint', 'Complaint'
        FEEDBACK = 'feedback', 'Feedback'
        VISIT = 'visit', 'Office Visit'

    customer = models.ForeignKey(
        'erp.Customer',
        on_delete=models.CASCADE,
        related_name='interactions'
    )
    interaction_type = models.CharField(max_length=20, choices=InteractionType.choices)
    subject = models.CharField(max_length=255)
    description = models.TextField()
    interaction_date = models.DateTimeField()
    
    handled_by = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_interactions'
    )
    
    # Follow-up
    requires_follow_up = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    is_follow_up_complete = models.BooleanField(default=False)

    class Meta:
        verbose_name=_('Customer Interaction')
        verbose_name_plural = 'Customer Interactions'
        ordering = ['-interaction_date']
        indexes = [
            models.Index(fields=['customer', 'interaction_date'], name='idx_ci_customer_date'),
            models.Index(fields=['interaction_type', 'interaction_date'], name='idx_ci_type_date'),
        ]

    def __str__(self):
        return f"{self.customer.name} - {self.subject}"


class Campaign(ERPBaseModel):
    """Marketing campaigns."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    class CampaignType(models.TextChoices):
        EMAIL = 'email', 'Email Marketing'
        SMS = 'sms', 'SMS Marketing'
        SOCIAL = 'social', 'Social Media'
        ADS = 'ads', 'Digital Advertising'
        EVENT = 'event', 'Event/Exhibition'
        REFERRAL = 'referral', 'Referral Program'
        OTHER = 'other', 'Other'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='campaigns'
    )
    
    name = models.CharField(max_length=255)
    campaign_type = models.CharField(max_length=20, choices=CampaignType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    
    # Dates
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Target
    target_audience = models.TextField(blank=True, help_text=_('Description of target audience'))
    
    # Budget
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns'
    )
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Goals
    expected_leads = models.PositiveIntegerField(default=0)
    expected_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Results
    actual_leads = models.PositiveIntegerField(default=0)
    actual_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Content
    description = models.TextField(blank=True)
    
    # Responsibility
    owner = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_campaigns'
    )

    class Meta:
        verbose_name=_('Campaign')
        verbose_name_plural = 'Campaigns'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['company', 'status'], name='idx_camp_company_status'),
            models.Index(fields=['company', 'campaign_type'], name='idx_camp_company_type'),
        ]

    def __str__(self):
        return self.name

    @property
    def roi(self):
        """Return on Investment as a percentage, rounded to 2 dp."""
        if self.actual_cost > 0:
            return (
                (self.actual_revenue - self.actual_cost)
                / self.actual_cost
                * 100
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0')


class CampaignLead(TimeStampedModel):
    """Track leads generated from campaigns."""
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='campaign_leads'
    )
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='campaign_sources'
    )

    class Meta:
        verbose_name=_('Campaign Lead')
        verbose_name_plural = 'Campaign Leads'
        unique_together = ['campaign', 'lead']

    def __str__(self):
        return f"{self.campaign.name} → {self.lead.full_name}"


class Task(ERPBaseModel):
    """General task management."""
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        ON_HOLD = 'on_hold', 'On Hold'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='tasks'
    )
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    
    # Assignment
    assigned_to = models.ForeignKey(
        'erp.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )
    
    # Dates
    due_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    # Related entities (polymorphic relationships)
    related_lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    related_customer = models.ForeignKey(
        'erp.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    # Reminder
    reminder_date = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)

    class Meta:
        verbose_name=_('Task')
        verbose_name_plural = 'Tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status', 'priority'], name='idx_task_company_status_pri'),
            models.Index(fields=['assigned_to', 'status'], name='idx_task_assigned_status'),
            models.Index(fields=['status', 'due_date'], name='idx_task_status_due'),
        ]
        constraints = [
            # A task may be linked to at most one related entity at a time
            # (either a lead OR a customer, never both simultaneously).
            models.CheckConstraint(
                condition=Q(related_lead__isnull=True) | Q(related_customer__isnull=True),
                name='task_single_related_object',
            ),
        ]

    def __str__(self):
        return self.title


class TaskComment(TimeStampedModel):
    """Comments on tasks."""
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_comments'
    )
    content = models.TextField()

    class Meta:
        verbose_name=_('Task Comment')
        verbose_name_plural = 'Task Comments'
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on {self.task.title}"
