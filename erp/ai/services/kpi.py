"""
KPI Anomaly Detection Service

Monitors key business metrics and generates alerts when values deviate
significantly from their historical norms (z-score > 2).
"""

import logging
from datetime import timedelta, date as dt_date
from decimal import Decimal

import numpy as np
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncDate
from django.utils import timezone

from erp.models import (
    Invoice, Payment, Expense, Lead, StockMovement, Customer,
)
from erp.ai.models import AIInsight
from .base import create_or_update_insight

logger = logging.getLogger('erp.ai.kpi')


class KPIAnomalyDetector:
    """Daily KPI health-check that detects statistically significant shifts."""

    def __init__(self, company):
        self.company = company
        self.lookback_days = 90

    def run_all_checks(self) -> list[dict]:
        """Run every KPI check and return generated alerts."""
        alerts = []
        for check in [
            self._check_daily_revenue,
            self._check_daily_expenses,
            self._check_new_leads,
            self._check_overdue_invoices,
            self._check_inventory_movements,
        ]:
            try:
                result = check()
                if result:
                    alerts.append(result)
            except Exception as exc:
                logger.exception('KPI check %s failed: %s', check.__name__, exc)
        return alerts

    # ── Individual checks ───────────────────────────────────────────────

    def _check_daily_revenue(self) -> dict | None:
        today = dt_date.today()
        yesterday = today - timedelta(days=1)
        since = yesterday - timedelta(days=self.lookback_days)

        daily = list(
            Invoice.objects.filter(
                company=self.company,
                status__in=['sent', 'partial', 'paid'],
                invoice_date__gte=since,
                invoice_date__lt=yesterday,
            ).annotate(day=TruncDate('invoice_date')).values('day').annotate(
                total=Sum('total_amount'),
            ).order_by('day').values_list('total', flat=True)
        )
        yesterday_rev = float(
            Invoice.objects.filter(
                company=self.company,
                invoice_date=yesterday,
                status__in=['sent', 'partial', 'paid'],
            ).aggregate(t=Sum('total_amount'))['t'] or 0
        )

        return self._z_check(
            'Daily Revenue', daily, yesterday_rev,
            category=AIInsight.Category.REVENUE,
            ref_date=yesterday,
        )

    def _check_daily_expenses(self) -> dict | None:
        today = dt_date.today()
        yesterday = today - timedelta(days=1)
        since = yesterday - timedelta(days=self.lookback_days)

        daily = list(
            Expense.objects.filter(
                company=self.company,
                status='approved',
                expense_date__gte=since,
                expense_date__lt=yesterday,
            ).annotate(day=TruncDate('expense_date')).values('day').annotate(
                total=Sum('total_amount'),
            ).order_by('day').values_list('total', flat=True)
        )
        yesterday_exp = float(
            Expense.objects.filter(
                company=self.company,
                expense_date=yesterday,
                status='approved',
            ).aggregate(t=Sum('total_amount'))['t'] or 0
        )

        return self._z_check(
            'Daily Expenses', daily, yesterday_exp,
            category=AIInsight.Category.EXPENSE,
            ref_date=yesterday,
        )

    def _check_new_leads(self) -> dict | None:
        today = dt_date.today()
        yesterday = today - timedelta(days=1)
        since = yesterday - timedelta(days=self.lookback_days)

        daily = list(
            Lead.objects.filter(
                company=self.company,
                created_at__date__gte=since,
                created_at__date__lt=yesterday,
            ).annotate(day=TruncDate('created_at')).values('day').annotate(
                cnt=Count('id'),
            ).order_by('day').values_list('cnt', flat=True)
        )
        yesterday_leads = Lead.objects.filter(
            company=self.company,
            created_at__date=yesterday,
        ).count()

        return self._z_check(
            'New Leads', daily, yesterday_leads,
            category=AIInsight.Category.CRM,
            ref_date=yesterday,
        )

    def _check_overdue_invoices(self) -> dict | None:
        overdue_count = Invoice.objects.filter(
            company=self.company,
            status='overdue',
        ).count()
        total_open = Invoice.objects.filter(
            company=self.company,
            status__in=['sent', 'partial', 'overdue'],
        ).count() or 1

        ratio = overdue_count / total_open
        if ratio > 0.3:
            title = f'High overdue ratio: {ratio:.0%} of open invoices'
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.REVENUE,
                severity=AIInsight.Severity.CRITICAL,
                title=title,
                description=(
                    f'{overdue_count} out of {total_open} open invoices are '
                    f'overdue ({ratio:.1%}). This exceeds the 30 % threshold.'
                ),
                recommendation='Prioritise collections and review credit policies.',
                action_url='/erp/finance/aging-receivables/',
            )
            return {
                'check': 'overdue_invoices',
                'severity': 'critical',
                'value': overdue_count,
                'ratio': round(ratio, 4),
            }
        else:
            # Condition cleared — auto-dismiss any stale overdue alerts
            AIInsight.objects.filter(
                company=self.company,
                category=AIInsight.Category.REVENUE,
                title__startswith='High overdue ratio',
                is_dismissed=False,
            ).update(is_dismissed=True, dismissed_at=timezone.now())
        return None

    def _check_inventory_movements(self) -> dict | None:
        today = dt_date.today()
        yesterday = today - timedelta(days=1)
        since = yesterday - timedelta(days=self.lookback_days)

        daily = list(
            StockMovement.objects.filter(
                company=self.company,
                created_at__date__gte=since,
                created_at__date__lt=yesterday,
            ).annotate(day=TruncDate('created_at')).values('day').annotate(
                cnt=Count('id'),
            ).order_by('day').values_list('cnt', flat=True)
        )
        yesterday_moves = StockMovement.objects.filter(
            company=self.company,
            created_at__date=yesterday,
        ).count()

        return self._z_check(
            'Inventory Movements', daily, yesterday_moves,
            category=AIInsight.Category.INVENTORY,
            ref_date=yesterday,
        )

    # ── Z-score helper ──────────────────────────────────────────────────

    def _z_check(self, metric_name: str, history: list,
                 check_value: float, category: str,
                 ref_date=None) -> dict | None:
        """Compare a day's value against the historical distribution.

        *ref_date* is the date being checked (defaults to yesterday).
        """
        if len(history) < 14:
            return None

        values = np.array([float(v) for v in history])
        mean = values.mean()
        std = values.std() or 1
        z = (check_value - mean) / std

        if abs(z) < 2.0:
            return None

        direction = 'above' if z > 0 else 'below'
        severity = (
            AIInsight.Severity.CRITICAL if abs(z) > 3
            else AIInsight.Severity.WARNING
        )

        ref_label = f' on {ref_date}' if ref_date else ''
        title = f'{metric_name} anomaly: {abs(z):.1f}σ {direction} average'

        create_or_update_insight(
            company=self.company,
            category=category,
            severity=severity,
            title=title,
            description=(
                f"{metric_name}{ref_label} ({check_value:,.2f}) is "
                f'{abs(z):.1f} standard deviations {direction} the '
                f'{self.lookback_days}-day average ({mean:,.2f}).'
            ),
            recommendation=f'Investigate the cause of the unusual {metric_name.lower()}.',
        )

        return {
            'check': metric_name,
            'severity': severity,
            'check_value': check_value,
            'mean': round(mean, 2),
            'std': round(std, 2),
            'z_score': round(z, 2),
        }
