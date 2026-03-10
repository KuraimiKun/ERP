"""
Tests for CRM models: Lead, LeadActivity, CustomerInteraction, Campaign, CampaignLead, Task.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.utils import timezone

from erp.models import (
    Lead, LeadActivity, CustomerInteraction,
    Campaign, CampaignLead, Task,
)
from erp.tests.helpers import ERPTestCase


# ────────────────────────────────────────────────────────────────
# Lead
# ────────────────────────────────────────────────────────────────

class LeadModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.lead = Lead.objects.create(
            company=cls.company,
            lead_number='LD-0001',
            first_name='Faisal',
            last_name='Al-Rashid',
            email='faisal@example.com',
            phone='0555555555',
            estimated_value=Decimal('50000.00'),
            created_by=cls.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.lead), 'Faisal Al-Rashid (LD-0001)')

    def test_full_name(self):
        self.assertEqual(self.lead.full_name, 'Faisal Al-Rashid')

    def test_default_status_is_new(self):
        self.assertEqual(self.lead.status, Lead.Status.NEW)

    def test_unique_lead_number(self):
        with self.assertRaises(IntegrityError):
            Lead.objects.create(
                company=self.company, lead_number='LD-0001',
                first_name='Dup', last_name='Dup',
                email='d@d.com', created_by=self.user,
            )

    def test_soft_delete_and_restore(self):
        self.lead.soft_delete(user=self.user)
        self.assertFalse(Lead.objects.filter(pk=self.lead.pk).exists())
        self.lead.restore()
        self.assertTrue(Lead.objects.filter(pk=self.lead.pk).exists())

    def test_source_choices(self):
        self.lead.source = Lead.Source.REFERRAL
        self.lead.save()
        self.assertEqual(self.lead.source, 'referral')

    def test_probability_default(self):
        self.assertEqual(self.lead.probability, 10)

    def test_assignment_to_employee(self):
        self.lead.assigned_to = self.employee
        self.lead.save()
        self.assertIn(self.lead, self.employee.assigned_leads.all())


# ────────────────────────────────────────────────────────────────
# Lead Activity
# ────────────────────────────────────────────────────────────────

class LeadActivityModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.lead = Lead.objects.create(
            company=cls.company, lead_number='LD-ACT',
            first_name='Test', last_name='Lead',
            email='t@t.com', created_by=cls.user,
        )

    def test_create_activity(self):
        act = LeadActivity.objects.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.CALL,
            subject='Follow-up call',
            description='Discussed pricing',
            activity_date=timezone.now(),
            performed_by=self.employee,
        )
        self.assertEqual(str(act), 'Phone Call - Follow-up call')
        self.assertFalse(act.is_completed)

    def test_complete_activity(self):
        act = LeadActivity.objects.create(
            lead=self.lead,
            activity_type=LeadActivity.ActivityType.MEETING,
            subject='Demo',
            activity_date=timezone.now(),
        )
        act.is_completed = True
        act.completed_date = timezone.now()
        act.save()
        self.assertTrue(act.is_completed)

    def test_activities_ordering(self):
        now = timezone.now()
        LeadActivity.objects.create(
            lead=self.lead, activity_type='call',
            subject='First', activity_date=now - timedelta(hours=2),
        )
        a2 = LeadActivity.objects.create(
            lead=self.lead, activity_type='email',
            subject='Second', activity_date=now,
        )
        activities = list(self.lead.activities.all())
        self.assertEqual(activities[0], a2)  # newest first


# ────────────────────────────────────────────────────────────────
# Customer Interaction
# ────────────────────────────────────────────────────────────────

class CustomerInteractionModelTest(ERPTestCase):

    def test_create_interaction(self):
        ci = CustomerInteraction.objects.create(
            customer=self.customer,
            interaction_type=CustomerInteraction.InteractionType.CALL,
            subject='Quarterly review',
            description='Reviewed Q1 numbers',
            interaction_date=timezone.now(),
            handled_by=self.employee,
        )
        self.assertIn(self.customer.name, str(ci))

    def test_follow_up_tracking(self):
        ci = CustomerInteraction.objects.create(
            customer=self.customer,
            interaction_type='email',
            subject='Proposal',
            description='Sent pricing proposal',
            interaction_date=timezone.now(),
            requires_follow_up=True,
            follow_up_date=timezone.now() + timedelta(days=7),
        )
        self.assertTrue(ci.requires_follow_up)
        self.assertFalse(ci.is_follow_up_complete)


# ────────────────────────────────────────────────────────────────
# Campaign
# ────────────────────────────────────────────────────────────────

class CampaignModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.campaign = Campaign.objects.create(
            company=cls.company,
            name='Summer Sale 2026',
            campaign_type=Campaign.CampaignType.EMAIL,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            budget=Decimal('10000.00'),
            actual_cost=Decimal('8000.00'),
            actual_revenue=Decimal('24000.00'),
            currency=cls.currency,
            created_by=cls.user,
        )

    def test_str_representation(self):
        self.assertEqual(str(self.campaign), 'Summer Sale 2026')

    def test_default_status(self):
        self.assertEqual(self.campaign.status, Campaign.Status.DRAFT)

    def test_roi_calculation(self):
        # ROI = (24000 - 8000) / 8000 * 100 = 200%
        self.assertEqual(self.campaign.roi, Decimal('200'))

    def test_roi_zero_cost(self):
        c = Campaign.objects.create(
            company=self.company, name='Free',
            campaign_type='social', start_date=date.today(),
            actual_cost=Decimal('0'), actual_revenue=Decimal('5000'),
            created_by=self.user,
        )
        self.assertEqual(c.roi, 0)

    def test_soft_delete(self):
        self.campaign.soft_delete(user=self.user)
        self.assertFalse(Campaign.objects.filter(pk=self.campaign.pk).exists())
        self.campaign.restore()
        self.assertTrue(Campaign.objects.filter(pk=self.campaign.pk).exists())


# ────────────────────────────────────────────────────────────────
# Campaign Lead (M2M through)
# ────────────────────────────────────────────────────────────────

class CampaignLeadModelTest(ERPTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.campaign = Campaign.objects.create(
            company=cls.company, name='Test Camp',
            campaign_type='email', start_date=date.today(),
            created_by=cls.user,
        )
        cls.lead = Lead.objects.create(
            company=cls.company, lead_number='LD-CL',
            first_name='CL', last_name='Test',
            email='cl@t.com', created_by=cls.user,
        )

    def test_create_campaign_lead(self):
        cl = CampaignLead.objects.create(
            campaign=self.campaign, lead=self.lead,
        )
        self.assertIn(self.campaign.name, str(cl))

    def test_unique_together(self):
        CampaignLead.objects.create(campaign=self.campaign, lead=self.lead)
        with self.assertRaises(IntegrityError):
            CampaignLead.objects.create(campaign=self.campaign, lead=self.lead)


# ────────────────────────────────────────────────────────────────
# Task
# ────────────────────────────────────────────────────────────────

class TaskModelTest(ERPTestCase):

    def test_create_task(self):
        task = Task.objects.create(
            company=self.company,
            title='Prepare proposal',
            description='For customer X',
            priority=Task.Priority.HIGH,
            assigned_to=self.employee,
            due_date=timezone.now() + timedelta(days=3),
            created_by=self.user,
        )
        self.assertEqual(task.status, Task.Status.TODO)

    def test_default_priority(self):
        task = Task.objects.create(
            company=self.company, title='Normal',
            created_by=self.user,
        )
        self.assertEqual(task.priority, Task.Priority.MEDIUM)

    def test_soft_delete_task(self):
        task = Task.objects.create(
            company=self.company, title='Delete me',
            created_by=self.user,
        )
        task.soft_delete(user=self.user)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())
        task.restore()
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_complete_task(self):
        task = Task.objects.create(
            company=self.company, title='Ship it',
            created_by=self.user,
        )
        task.status = Task.Status.COMPLETED
        task.completed_date = timezone.now()
        task.save()
        self.assertEqual(task.status, 'completed')
