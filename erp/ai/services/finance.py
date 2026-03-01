"""
Financial ML Services

1. Late-Payment Risk Prediction   – per-invoice probability of late payment
2. Expense Anomaly Detection      – flag outlier expenses
3. Cash-Flow Forecasting          – 30/60/90-day cash-position projection
"""

import logging
from decimal import Decimal
from datetime import timedelta, date as dt_date

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.preprocessing import LabelEncoder
from django.conf import settings
from django.db.models import Sum, Avg, Count, F, Q, ExpressionWrapper, fields
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone

from erp.models import (
    Invoice, Payment, PaymentAllocation, Expense, Customer,
    PurchaseOrder, SupplierInvoice,
)
from erp.ai.models import MLModel, AIInsight
from .base import (
    get_or_create_registry, save_model_artefact, load_model_artefact,
    log_prediction, bump_version, create_or_update_insight, logger,
)

logger = logging.getLogger('erp.ai.finance')


# ════════════════════════════════════════════════════════════════════════════
# 1.  Late-Payment Risk Prediction
# ════════════════════════════════════════════════════════════════════════════

class LatePaymentPredictor:
    """Gradient Boosted classifier that scores the probability an invoice
    will *not* be paid by its due date."""

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, 'ML_MIN_TRAINING_SAMPLES', 30)
        self._model = None
        self._registry = None

    # ── Feature Engineering ─────────────────────────────────────────────

    def _build_dataset(self) -> pd.DataFrame:
        """Build a labelled dataset from closed invoices."""
        invoices = Invoice.objects.filter(
            company=self.company,
            status__in=['paid', 'overdue', 'partial'],
            due_date__isnull=False,
        ).select_related('customer').values(
            'id', 'customer_id', 'total_amount', 'invoice_date',
            'due_date', 'status', 'customer__customer_type',
        )
        df = pd.DataFrame(list(invoices))
        if df.empty or len(df) < self.min_samples:
            return pd.DataFrame()

        # Label: 1 = was paid late (or still overdue)
        # Look up the first payment date for each invoice
        payment_dates = {}
        for inv_id in df['id'].unique():
            first_pay = Payment.objects.filter(
                company=self.company,
                allocations__invoice_id=inv_id,
            ).order_by('payment_date').values_list('payment_date', flat=True).first()
            payment_dates[inv_id] = first_pay

        df['first_payment_date'] = df['id'].map(payment_dates)
        df['late'] = 0
        mask_overdue = df['status'] == 'overdue'
        mask_paid_late = (
            df['first_payment_date'].notna()
            & (df['first_payment_date'] > df['due_date'])
        )
        df.loc[mask_overdue | mask_paid_late, 'late'] = 1

        # Features
        df['invoice_amount'] = df['total_amount'].astype(float)
        df['days_to_due'] = (
            pd.to_datetime(df['due_date']) - pd.to_datetime(df['invoice_date'])
        ).dt.days
        df['invoice_month'] = pd.to_datetime(df['invoice_date']).dt.month

        # Customer historical stats
        customer_stats = (
            df.groupby('customer_id')
            .agg(
                cust_total_invoices=('id', 'count'),
                cust_avg_amount=('invoice_amount', 'mean'),
                cust_late_ratio=('late', 'mean'),
            )
            .reset_index()
        )
        df = df.merge(customer_stats, on='customer_id', how='left')

        # Encode customer type
        df['customer_type_code'] = df['customer__customer_type'].astype(
            'category').cat.codes

        feature_cols = [
            'invoice_amount', 'days_to_due', 'invoice_month',
            'cust_total_invoices', 'cust_avg_amount', 'cust_late_ratio',
            'customer_type_code',
        ]
        df[feature_cols] = df[feature_cols].fillna(0)
        return df

    # ── Training ────────────────────────────────────────────────────────

    def train(self) -> dict:
        """Train (or retrain) the late-payment model."""
        df = self._build_dataset()
        if df.empty:
            logger.info('Insufficient data for late-payment model (company %d)',
                        self.company.pk)
            return {'status': 'skipped', 'reason': 'insufficient_data'}

        feature_cols = [
            'invoice_amount', 'days_to_due', 'invoice_month',
            'cust_total_invoices', 'cust_avg_amount', 'cust_late_ratio',
            'customer_type_code',
        ]
        X = df[feature_cols].values
        y = df['late'].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y,
        )

        clf = GradientBoostingClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            subsample=0.8, random_state=42,
        )
        clf.fit(X_train, y_train)

        y_proba = clf.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 else 0.0

        # Persist
        registry = get_or_create_registry(
            self.company, MLModel.ModelType.LATE_PAYMENT,
            'Late Payment Predictor',
        )
        registry.training_samples = len(df)
        registry.accuracy_score = auc
        registry.parameters = {'feature_cols': feature_cols}
        save_model_artefact(registry, {
            'classifier': clf,
            'feature_cols': feature_cols,
        })

        self._model = clf
        self._registry = registry

        logger.info('Late-payment model trained: AUC=%.4f samples=%d',
                     auc, len(df))
        return {
            'status': 'trained',
            'auc': round(auc, 4),
            'samples': len(df),
        }

    # ── Prediction ──────────────────────────────────────────────────────

    def _load(self):
        if self._model is not None:
            return
        self._registry = get_or_create_registry(
            self.company, MLModel.ModelType.LATE_PAYMENT,
            'Late Payment Predictor',
        )
        if not self._registry.artefact_path:
            self.train()
            return
        artefact = load_model_artefact(self._registry)
        self._model = artefact['classifier']

    def predict(self, invoice: Invoice) -> float:
        """Return the probability (0–1) that an invoice will be paid late."""
        self._load()
        if self._model is None:
            return 0.0

        # Build feature vector
        cust = invoice.customer
        cust_invoices = Invoice.objects.filter(
            company=self.company, customer=cust,
        )
        cust_total = cust_invoices.count() or 1
        cust_avg_amount = float(
            cust_invoices.aggregate(avg=Avg('total_amount'))['avg'] or 0
        )
        cust_late = cust_invoices.filter(status='overdue').count() / cust_total

        features = np.array([[
            float(invoice.total_amount),
            (invoice.due_date - invoice.invoice_date).days if invoice.due_date else 30,
            invoice.invoice_date.month,
            cust_total,
            cust_avg_amount,
            cust_late,
            {'individual': 0, 'company': 1, 'government': 2}.get(
                cust.customer_type, 0),
        ]])

        prob = float(self._model.predict_proba(features)[0][1])

        log_prediction(self._registry, 'Invoice', invoice.pk, prob, {
            'invoice_number': invoice.invoice_number,
            'customer': cust.name,
            'amount': float(invoice.total_amount),
        })

        return prob

    def score_all_open_invoices(self) -> list[dict]:
        """Score every open invoice and return results."""
        self._load()
        if self._model is None:
            return []

        invoices = Invoice.objects.filter(
            company=self.company,
            status__in=['sent', 'partial'],
            due_date__isnull=False,
        ).select_related('customer')

        results = []
        for inv in invoices:
            try:
                risk = self.predict(inv)
                results.append({
                    'invoice_id': inv.pk,
                    'invoice_number': inv.invoice_number,
                    'customer': inv.customer.name,
                    'amount': float(inv.total_amount),
                    'due_date': str(inv.due_date),
                    'risk_score': round(risk, 4),
                    'risk_level': (
                        'high' if risk > 0.7
                        else 'medium' if risk > 0.4
                        else 'low'
                    ),
                })
            except Exception as exc:
                logger.exception('Risk scoring failed for invoice %d: %s',
                                 inv.pk, exc)

        # Create insight for high-risk invoices
        high_risk = [r for r in results if r['risk_level'] == 'high']
        if high_risk:
            title = f'{len(high_risk)} invoices at high risk of late payment'
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.REVENUE,
                severity=AIInsight.Severity.WARNING,
                title=title,
                description=(
                    'The following invoices have a >70 % probability of being '
                    'paid late: '
                    + ', '.join(f"{r['invoice_number']} ({r['customer']})"
                                for r in high_risk[:10])
                ),
                recommendation=(
                    'Consider sending early reminders or offering early-payment '
                    'discounts for these customers.'
                ),
                action_url='/erp/invoices/',
            )

        return results


# ════════════════════════════════════════════════════════════════════════════
# 2.  Expense Anomaly Detection
# ════════════════════════════════════════════════════════════════════════════

class ExpenseAnomalyDetector:
    """Uses Isolation Forest to flag unusual expenses."""

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, 'ML_MIN_TRAINING_SAMPLES', 30)

    def detect(self) -> list[dict]:
        """Scan approved expenses and return anomalies."""
        qs = Expense.objects.filter(
            company=self.company,
        ).select_related('category').values(
            'id', 'expense_number', 'total_amount',
            'expense_date', 'category__name', 'status',
        )
        df = pd.DataFrame(list(qs))
        if len(df) < self.min_samples:
            return []

        df['amount'] = df['total_amount'].astype(float)
        df['month'] = pd.to_datetime(df['expense_date']).dt.month
        df['day_of_week'] = pd.to_datetime(df['expense_date']).dt.dayofweek

        le = LabelEncoder()
        df['category_code'] = le.fit_transform(
            df['category__name'].fillna('Unknown'))

        features = df[['amount', 'month', 'day_of_week', 'category_code']].values

        iso = IsolationForest(
            contamination=0.05, random_state=42, n_estimators=200,
        )
        predictions = iso.fit_predict(features)
        scores = iso.decision_function(features)

        df['is_anomaly'] = predictions == -1
        df['anomaly_score'] = scores

        anomalies = df[df['is_anomaly']].sort_values('anomaly_score')
        results = []
        for _, row in anomalies.iterrows():
            results.append({
                'expense_id': int(row['id']),
                'expense_number': row['expense_number'],
                'amount': row['amount'],
                'category': row['category__name'],
                'date': str(row['expense_date']),
                'anomaly_score': round(float(row['anomaly_score']), 4),
            })

        if results:
            title = f'{len(results)} expense anomalies detected'
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.EXPENSE,
                severity=AIInsight.Severity.WARNING,
                title=title,
                description=(
                    'Isolation Forest flagged the following expenses: '
                    + ', '.join(f"{r['expense_number']} ({r['amount']:.2f})"
                                for r in results[:10])
                ),
                recommendation=(
                    'Review flagged expenses for potential errors, '
                    'policy violations, or fraud.'
                ),
                action_url='/erp/expenses/',
            )

        return results


# ════════════════════════════════════════════════════════════════════════════
# 3.  Cash-Flow Forecasting
# ════════════════════════════════════════════════════════════════════════════

class CashFlowForecaster:
    """Projects net cash position for the next 30 / 60 / 90 days."""

    def __init__(self, company):
        self.company = company

    def forecast(self, periods: int = 90) -> dict:
        """Return a day-by-day cash-flow projection.

        Returns dict with keys: dates, inflows, outflows, net, cumulative.
        """
        today = dt_date.today()
        dates = [today + timedelta(days=i) for i in range(periods)]

        # ── Expected inflows (outstanding invoices by due date) ─────────
        inflows = self._expected_inflows(today, periods)

        # ── Expected outflows (PO + supplier invoices + recurring expenses)
        outflows = self._expected_outflows(today, periods)

        # Build daily series
        inflow_series = np.zeros(periods)
        outflow_series = np.zeros(periods)

        for item in inflows:
            delta = (item['date'] - today).days
            if 0 <= delta < periods:
                inflow_series[delta] += item['amount']

        for item in outflows:
            delta = (item['date'] - today).days
            if 0 <= delta < periods:
                outflow_series[delta] += item['amount']

        net_series = inflow_series - outflow_series
        cumulative = np.cumsum(net_series)

        # Summary at 30 / 60 / 90 days
        summary = {}
        for horizon in [30, 60, 90]:
            if horizon <= periods:
                summary[f'{horizon}d'] = {
                    'inflows': round(float(inflow_series[:horizon].sum()), 2),
                    'outflows': round(float(outflow_series[:horizon].sum()), 2),
                    'net': round(float(net_series[:horizon].sum()), 2),
                    'cumulative': round(float(cumulative[horizon - 1]), 2),
                }

        # Create insight if negative cumulative
        if cumulative.min() < 0:
            first_neg_day = int(np.argmax(cumulative < 0))
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.CASH_FLOW,
                severity=AIInsight.Severity.CRITICAL,
                title='Projected negative cash flow',
                description=(
                    f'Cash-flow projection shows a negative position starting '
                    f'day {first_neg_day + 1} ({dates[first_neg_day]}). '
                    f'Lowest point: {cumulative.min():,.2f}'
                ),
                recommendation=(
                    'Consider accelerating receivables collection, '
                    'negotiating extended payment terms with suppliers, '
                    'or arranging a credit facility.'
                ),
                action_url='/erp/ai/cashflow/',
            )

        return {
            'dates': [d.isoformat() for d in dates],
            'inflows': inflow_series.round(2).tolist(),
            'outflows': outflow_series.round(2).tolist(),
            'net': net_series.round(2).tolist(),
            'cumulative': cumulative.round(2).tolist(),
            'summary': summary,
        }

    def _expected_inflows(self, today, periods):
        """Outstanding invoices expected to be paid by due date."""
        end = today + timedelta(days=periods)
        invoices = Invoice.objects.filter(
            company=self.company,
            status__in=['sent', 'partial'],
            due_date__gte=today,
            due_date__lte=end,
        ).values('due_date', 'balance_due')

        return [
            {'date': row['due_date'], 'amount': float(row['balance_due'])}
            for row in invoices
        ]

    def _expected_outflows(self, today, periods):
        """POs and supplier invoices due in the period."""
        end = today + timedelta(days=periods)
        items = []

        # Supplier invoices
        si_qs = SupplierInvoice.objects.filter(
            company=self.company,
            status__in=['pending', 'partial'],
            due_date__gte=today,
            due_date__lte=end,
        ).values('due_date', 'balance_due')
        for row in si_qs:
            items.append({
                'date': row['due_date'],
                'amount': float(row['balance_due']),
            })

        # Open purchase orders (estimated delivery = today + lead time)
        po_qs = PurchaseOrder.objects.filter(
            company=self.company,
            status__in=['approved', 'sent'],
        ).values('order_date', 'total_amount')
        for row in po_qs:
            est_date = row['order_date'] + timedelta(days=14)  # default lead
            if today <= est_date <= end:
                items.append({
                    'date': est_date,
                    'amount': float(row['total_amount']),
                })

        return items
