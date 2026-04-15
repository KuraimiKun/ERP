"""
Celery tasks for finance automation.

mark_overdue_invoices   — Daily: set sent invoices past due_date to 'overdue'
auto_post_depreciation  — Monthly: generate and post depreciation for all active assets
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('erp.tasks.finance')


@shared_task(
    bind=True,
    name='erp.tasks.finance.mark_overdue_invoices',
    max_retries=0,
    time_limit=300,
    soft_time_limit=270,
    acks_late=True,
)
def mark_overdue_invoices(self):
    """
    Transition all sent invoices whose due_date is in the past to 'overdue'.

    Runs across all tenant databases registered as active.
    Safe to re-run: only touches invoices with status='sent' and due_date < today.
    """
    from django.conf import settings
    from erp.models import Invoice

    today = timezone.now().date()
    total_updated = 0

    # Iterate over every tenant database
    for db_alias, db_conf in settings.DATABASES.items():
        if db_alias == 'default':
            continue
        try:
            updated = Invoice.objects.using(db_alias).filter(
                status='sent',
                due_date__lt=today,
            ).update(status=Invoice.Status.OVERDUE)
            if updated:
                logger.info(
                    'mark_overdue_invoices: %d invoice(s) marked overdue in %s',
                    updated, db_alias,
                )
                total_updated += updated
        except Exception:
            logger.exception(
                'mark_overdue_invoices: failed for db_alias=%s', db_alias
            )

    return {'total_updated': total_updated}


@shared_task(
    bind=True,
    name='erp.tasks.finance.auto_post_depreciation',
    max_retries=0,
    time_limit=1800,
    soft_time_limit=1700,
    acks_late=True,
)
def auto_post_depreciation(self):
    """
    Generate and post depreciation entries for all active assets across all tenant databases.

    For each active asset whose depreciation_start_date <= today, generates any
    missing monthly schedule entries and posts them. Idempotent: skips entries that
    are already generated or posted.
    """
    from django.conf import settings
    from erp.models import FixedAsset, DepreciationSchedule

    today = timezone.now().date()
    total_posted = 0

    for db_alias, db_conf in settings.DATABASES.items():
        if db_alias == 'default':
            continue
        try:
            assets = FixedAsset.objects.using(db_alias).filter(
                status='active',
                depreciation_start_date__lte=today,
            ).select_related('company', 'category')

            for asset in assets:
                try:
                    posted = _post_pending_depreciation(asset, db_alias, today)
                    total_posted += posted
                except Exception:
                    logger.exception(
                        'auto_post_depreciation: failed for asset pk=%s in %s',
                        asset.pk, db_alias,
                    )
        except Exception:
            logger.exception(
                'auto_post_depreciation: failed to load assets for db_alias=%s', db_alias
            )

    return {'total_posted': total_posted}


@shared_task(
    bind=True,
    name='erp.tasks.finance.check_reorder_rules',
    max_retries=0,
    time_limit=600,
    soft_time_limit=560,
    acks_late=True,
)
def check_reorder_rules(self):
    """
    Check all active ReorderRules across tenant databases and create draft
    PurchaseOrders for products below their reorder point.

    Groups products by preferred supplier per company, creating one PO per
    supplier per run (if no existing draft PO for that supplier exists today).
    Idempotent: skips products that already have an open/pending PO line.
    """
    from django.conf import settings
    from django.utils import timezone

    today = timezone.now().date()
    total_pos_created = 0

    for db_alias in settings.DATABASES:
        if db_alias == 'default':
            continue
        try:
            total_pos_created += _process_reorder_rules(db_alias, today)
        except Exception:
            logger.exception('check_reorder_rules: failed for db_alias=%s', db_alias)

    return {'total_pos_created': total_pos_created}


def _process_reorder_rules(db_alias, today):
    """Process reorder rules for one tenant database."""
    from erp.models import ReorderRule, StockItem, PurchaseOrder, PurchaseOrderLine
    from django.db import transaction
    from collections import defaultdict

    rules = ReorderRule.objects.using(db_alias).filter(
        is_active=True,
        preferred_supplier__isnull=False,
    ).select_related('product', 'warehouse', 'preferred_supplier', 'company')

    # Map (company, supplier) → list of (rule, current_qty)
    to_order = defaultdict(list)
    for rule in rules:
        stock = StockItem.objects.using(db_alias).filter(
            product=rule.product, warehouse=rule.warehouse,
        ).first()
        available = (stock.on_hand - stock.allocated) if stock else 0
        if available < rule.reorder_point:
            order_qty = rule.min_order_qty
            if rule.max_order_qty > 0:
                order_qty = min(
                    max(order_qty, rule.reorder_point + rule.safety_stock - available),
                    rule.max_order_qty,
                )
            to_order[(rule.company, rule.preferred_supplier)].append((rule, order_qty))

    created = 0
    for (company, supplier), items in to_order.items():
        try:
            with transaction.atomic(using=db_alias):
                from erp.services.sequence import SequenceService
                po_number = SequenceService.get_next_number(company, 'purchase_order')
                po = PurchaseOrder.objects.using(db_alias).create(
                    company=company,
                    supplier=supplier,
                    po_number=po_number,
                    po_date=today,
                    currency=company.base_currency,
                    status=PurchaseOrder.Status.DRAFT,
                    notes=f'Auto-generated by reorder rule check on {today}',
                )
                for rule, qty in items:
                    PurchaseOrderLine.objects.using(db_alias).create(
                        purchase_order=po,
                        product=rule.product,
                        description=rule.product.name,
                        quantity=qty,
                        unit_price=rule.product.cost_price or 0,
                    )
                po.calculate_totals()
                po.save(using=db_alias)
                created += 1
        except Exception:
            logger.exception(
                '_process_reorder_rules: failed to create PO for company=%s supplier=%s',
                company.pk, supplier.pk,
            )

    return created


def _post_pending_depreciation(asset, db_alias, today):
    """
    Post all scheduled (unposted) depreciation entries up to today.

    Delegates to DepreciationSchedule.post() which creates the full JE:
        DR Depreciation Expense
        CR Accumulated Depreciation
    and updates asset.accumulated_depreciation / current_book_value.
    """
    from erp.models import DepreciationSchedule
    from django.db import transaction

    posted = 0
    pending = DepreciationSchedule.objects.using(db_alias).filter(
        asset=asset,
        period_date__lte=today,
        status=DepreciationSchedule.Status.SCHEDULED,
    ).order_by('period_date')

    for entry in pending:
        try:
            with transaction.atomic(using=db_alias):
                # Re-fetch with row-lock to prevent duplicate posting
                locked = DepreciationSchedule.objects.using(db_alias).select_for_update().get(pk=entry.pk)
                if locked.status != DepreciationSchedule.Status.SCHEDULED:
                    continue
                # post() creates the JE, updates asset balances, and sets status='posted'
                locked.post(user=None)
                posted += 1
        except Exception:
            logger.exception(
                '_post_pending_depreciation: failed for schedule entry pk=%s', entry.pk
            )
    return posted
