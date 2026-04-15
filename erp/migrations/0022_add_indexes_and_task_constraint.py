"""
Migration: add missing DB indexes and Task polymorphic FK constraint.

- Invoice: two new composite indexes for overdue/aging reports
- Lead: new composite index for rep workload views
- Task: CheckConstraint ensuring related_lead and related_customer are
        mutually exclusive (at most one may be non-null at a time)
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0021_account_idx_acct_company_type_active_and_more'),
    ]

    operations = [
        # ── Invoice overdue / aging indexes ─────────────────────────────────
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(
                fields=['company', 'balance_due', 'status'],
                name='idx_inv_company_balance_status',
            ),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(
                fields=['customer', 'status', 'invoice_date'],
                name='idx_inv_customer_status_date',
            ),
        ),

        # ── Lead rep-workload index ──────────────────────────────────────────
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(
                fields=['assigned_to', 'status', 'next_follow_up'],
                name='idx_lead_rep_workload',
            ),
        ),

        # ── Task polymorphic FK constraint ───────────────────────────────────
        migrations.AddConstraint(
            model_name='task',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(related_lead__isnull=True) |
                    models.Q(related_customer__isnull=True)
                ),
                name='task_single_related_object',
            ),
        ),
    ]
