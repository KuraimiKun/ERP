"""
Financial ML Services

1. Late-Payment Risk Prediction   – per-invoice probability of late payment
2. Expense Anomaly Detection      – flag outlier expenses
3. Cash-Flow Forecasting          – 30/60/90-day cash-position projection
"""

import logging
from datetime import timedelta, date as dt_date

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.preprocessing import LabelEncoder
from django.conf import settings
from django.db.models import Avg

from erp.models import (
    Invoice,
    PaymentAllocation,
    Expense,
    PurchaseOrder,
    SupplierInvoice,
)
from erp.ai.models import MLModel, AIInsight
from .base import (
    get_or_create_registry,
    save_model_artefact,
    load_model_artefact,
    log_prediction,
    create_or_update_insight,
)

logger = logging.getLogger("erp.ai.finance")


# ════════════════════════════════════════════════════════════════════════════
# 1.  Late-Payment Risk Prediction
# ════════════════════════════════════════════════════════════════════════════


class LatePaymentPredictor:
    """Gradient Boosted classifier that scores the probability an invoice
    will *not* be paid by its due date."""

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, "ML_MIN_TRAINING_SAMPLES", 30)
        self._model = None
        self._registry = None

    # ── Feature Engineering ─────────────────────────────────────────────

    FEATURE_COLS = [
        "invoice_amount",
        "amount_log",
        "days_to_due",
        "invoice_month",
        "month_sin",
        "month_cos",
        "invoice_day_of_week",
        "invoice_quarter",
        "cust_total_invoices",
        "cust_avg_amount",
        "cust_avg_days_to_due",
        "cust_payment_delay_mean",
        "cust_late_ratio",
        "customer_type_code",
        "amount_vs_cust_avg",
        "amount_percentile",
        "is_large_invoice",
        "payment_term_bucket",
    ]

    def _build_dataset(self) -> pd.DataFrame:
        """Build a labelled dataset from closed invoices.

        IMPORTANT: We avoid data-leaking features (e.g. per-customer
        late-payment ratio computed from ALL rows).  Instead we use
        leave-one-out historical statistics that a model would realistically
        have at prediction time.
        """
        invoices = (
            Invoice.objects.filter(
                company=self.company,
                status__in=["paid", "overdue", "partial"],
                due_date__isnull=False,
            )
            .select_related("customer")
            .values(
                "id",
                "customer_id",
                "total_amount",
                "invoice_date",
                "due_date",
                "status",
                "customer__customer_type",
                "paid_amount",
                "balance_due",
            )
        )
        df = pd.DataFrame(list(invoices))
        if df.empty or len(df) < self.min_samples:
            return pd.DataFrame()

        # ── Label ───────────────────────────────────────────────────────
        # 1 = paid late (first payment after due date) OR still overdue
        # Batch-fetch first payment date per invoice via PaymentAllocation
        from django.db.models import Min

        alloc_qs = (
            PaymentAllocation.objects.filter(
                invoice_id__in=df["id"].tolist(),
            )
            .values("invoice_id")
            .annotate(
                first_pay=Min("payment__payment_date"),
            )
        )
        payment_dates = {r["invoice_id"]: r["first_pay"] for r in alloc_qs}

        df["first_payment_date"] = df["id"].map(payment_dates)
        df["late"] = 0
        mask_overdue = df["status"] == "overdue"
        mask_paid_late = df["first_payment_date"].notna() & (
            pd.to_datetime(df["first_payment_date"]) > pd.to_datetime(df["due_date"])
        )
        df.loc[mask_overdue | mask_paid_late, "late"] = 1

        # ── Basic Features ──────────────────────────────────────────────
        df["invoice_amount"] = df["total_amount"].astype(float)
        df["invoice_date_dt"] = pd.to_datetime(df["invoice_date"])
        df["due_date_dt"] = pd.to_datetime(df["due_date"])
        df["days_to_due"] = (df["due_date_dt"] - df["invoice_date_dt"]).dt.days
        df["invoice_month"] = df["invoice_date_dt"].dt.month
        df["invoice_day_of_week"] = df["invoice_date_dt"].dt.dayofweek

        # ── Customer Features (NO label leakage) ────────────────────────
        # Sort by invoice_date so we can compute expanding (cumulative) stats
        df = df.sort_values("invoice_date_dt").reset_index(drop=True)

        # Cumulative count of invoices per customer (excluding current)
        df["cust_total_invoices"] = df.groupby("customer_id").cumcount()  # 0-based count before this row
        # Expanding mean of amount (excluding current row → shift)
        df["cust_avg_amount"] = (
            df.groupby("customer_id")["invoice_amount"].transform(lambda s: s.expanding().mean().shift(1))
        ).fillna(0)
        # Expanding mean of days_to_due
        df["cust_avg_days_to_due"] = (
            df.groupby("customer_id")["days_to_due"].transform(lambda s: s.expanding().mean().shift(1))
        ).fillna(0)

        # Historical average payment delay per customer
        # (only using invoices chronologically BEFORE the current one)
        df["payment_delay"] = np.nan
        paid_mask = df["first_payment_date"].notna()
        df.loc[paid_mask, "payment_delay"] = (
            pd.to_datetime(df.loc[paid_mask, "first_payment_date"]) - df.loc[paid_mask, "due_date_dt"]
        ).dt.days.astype(float)
        df["cust_payment_delay_mean"] = (
            df.groupby("customer_id")["payment_delay"].transform(lambda s: s.expanding().mean().shift(1))
        ).fillna(0)

        # Amount relative to customer average
        df["amount_vs_cust_avg"] = (df["invoice_amount"] / df["cust_avg_amount"].clip(lower=0.01)).clip(0, 10).fillna(1)

        # Encode customer type
        df["customer_type_code"] = df["customer__customer_type"].astype("category").cat.codes

        # ── New features for better generalisation ──────────────────────
        # Log-transformed amount (reduces skew)
        df["amount_log"] = np.log1p(df["invoice_amount"])

        # Cyclical month encoding (captures Jan-Dec wrap-around)
        df["month_sin"] = np.sin(2 * np.pi * df["invoice_month"] / 12)
        df["month_cos"] = np.cos(2 * np.pi * df["invoice_month"] / 12)

        # Quarter of year
        df["invoice_quarter"] = df["invoice_date_dt"].dt.quarter

        # Amount percentile (rank-based, robust to distribution shape)
        df["amount_percentile"] = df["invoice_amount"].rank(pct=True)

        # Is large invoice (top 25%)
        q75 = df["invoice_amount"].quantile(0.75)
        df["is_large_invoice"] = (df["invoice_amount"] >= q75).astype(int)

        # Payment term bucket (short / medium / long / very_long)
        df["payment_term_bucket"] = pd.cut(
            df["days_to_due"],
            bins=[-np.inf, 15, 30, 60, np.inf],
            labels=[0, 1, 2, 3],
        ).astype(int)

        # Balance ratio (balance_due / total_amount) - captures partial pay
        df["balance_ratio"] = (
            (df["balance_due"].astype(float) / df["total_amount"].astype(float).clip(lower=0.01)).clip(0, 1).fillna(1)
        )

        # Historical late-payment ratio per customer (expanding + shift)
        df["cust_late_ratio"] = (
            df.groupby("customer_id")["late"].transform(lambda s: s.expanding().mean().shift(1))
        ).fillna(0)

        df[self.FEATURE_COLS] = df[self.FEATURE_COLS].fillna(0)
        return df

    # ── Training ────────────────────────────────────────────────────────

    def train(self) -> dict:
        """Train (or retrain) the late-payment model."""
        df = self._build_dataset()
        if df.empty:
            logger.info("Insufficient data for late-payment model (company %d)", self.company.pk)
            return {"status": "skipped", "reason": "insufficient_data"}

        X = df[self.FEATURE_COLS].values
        y = df["late"].values

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y,
        )

        # Compute sample weights to handle class imbalance
        late_ratio = y_train.mean()
        weights = np.where(
            y_train == 1,
            1.0 / max(late_ratio, 0.01),
            1.0 / max(1 - late_ratio, 0.01),
        )

        clf = GradientBoostingClassifier(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=15,
            random_state=42,
            max_features="sqrt",
            validation_fraction=0.1,
            n_iter_no_change=30,
            tol=1e-4,
        )
        clf.fit(X_train, y_train, sample_weight=weights)

        y_proba = clf.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_proba) if len(set(y_test)) > 1 else 0.0

        # Feature importance for interpretability
        feat_imp = dict(zip(self.FEATURE_COLS, clf.feature_importances_.round(4).tolist()))

        # Persist
        registry = get_or_create_registry(
            self.company,
            MLModel.ModelType.LATE_PAYMENT,
            "Late Payment Predictor",
        )
        registry.training_samples = len(df)
        registry.accuracy_score = auc
        registry.parameters = {
            "feature_cols": self.FEATURE_COLS,
            "feature_importance": feat_imp,
            "late_ratio": round(float(y.mean()), 4),
            "class_report": classification_report(
                y_test,
                (y_proba > 0.5).astype(int),
                output_dict=True,
            ),
        }
        save_model_artefact(
            registry,
            {
                "classifier": clf,
                "feature_cols": self.FEATURE_COLS,
            },
        )

        self._model = clf
        self._registry = registry

        logger.info("Late-payment model trained: AUC=%.4f samples=%d late_ratio=%.2f%%", auc, len(df), y.mean() * 100)
        return {
            "status": "trained",
            "auc": round(auc, 4),
            "samples": len(df),
            "late_ratio": round(float(y.mean()), 4),
            "feature_importance": feat_imp,
        }

    # ── Prediction ──────────────────────────────────────────────────────

    def _load(self):
        if self._model is not None:
            return
        self._registry = get_or_create_registry(
            self.company,
            MLModel.ModelType.LATE_PAYMENT,
            "Late Payment Predictor",
        )
        if not self._registry.artefact_path:
            self.train()
            return
        artefact = load_model_artefact(self._registry)
        self._model = artefact["classifier"]

    def _build_single_feature_vector(self, invoice: Invoice) -> np.ndarray | None:
        """Build the feature vector for a single invoice.

        Returns a (1, n_features) numpy array matching FEATURE_COLS order,
        or None if features cannot be built.
        Used by both predict() and the XAI explainability service.
        """
        cust = invoice.customer

        past_invoices = Invoice.objects.filter(
            company=self.company,
            customer=cust,
            invoice_date__lt=invoice.invoice_date,
        )
        cust_total = past_invoices.count()
        cust_avg_amount = float(past_invoices.aggregate(avg=Avg("total_amount"))["avg"] or 0)
        past_vals = past_invoices.filter(due_date__isnull=False).values_list("invoice_date", "due_date")
        avg_dtd = np.mean([(dd - id).days for id, dd in past_vals]) if past_vals else 0.0

        from django.db.models import Min

        past_ids = list(past_invoices.values_list("id", flat=True)[:500])
        if past_ids:
            delays = []
            allocs = (
                PaymentAllocation.objects.filter(
                    invoice_id__in=past_ids,
                )
                .values("invoice_id")
                .annotate(
                    first_pay=Min("payment__payment_date"),
                )
            )
            inv_dues = dict(
                past_invoices.filter(
                    id__in=[a["invoice_id"] for a in allocs],
                ).values_list("id", "due_date")
            )
            for a in allocs:
                dd = inv_dues.get(a["invoice_id"])
                if dd and a["first_pay"]:
                    delays.append((a["first_pay"] - dd).days)
            cust_delay_mean = np.mean(delays) if delays else 0.0
        else:
            cust_delay_mean = 0.0

        days_to_due = (invoice.due_date - invoice.invoice_date).days if invoice.due_date else 30
        inv_amount = float(invoice.total_amount)
        amount_vs_avg = inv_amount / max(cust_avg_amount, 0.01) if cust_avg_amount > 0 else 1.0
        month = invoice.invoice_date.month

        if past_ids:
            past_late_count = Invoice.objects.filter(
                id__in=past_ids,
                status="overdue",
            ).count()
            cust_late_ratio = past_late_count / max(len(past_ids), 1)
        else:
            cust_late_ratio = 0.0

        return np.array(
            [
                [
                    inv_amount,
                    np.log1p(inv_amount),
                    days_to_due,
                    month,
                    np.sin(2 * np.pi * month / 12),
                    np.cos(2 * np.pi * month / 12),
                    invoice.invoice_date.weekday(),
                    (month - 1) // 3 + 1,
                    cust_total,
                    cust_avg_amount,
                    avg_dtd,
                    cust_delay_mean,
                    cust_late_ratio,
                    {"individual": 0, "company": 1, "government": 2}.get(cust.customer_type, 0),
                    min(amount_vs_avg, 10.0),
                    0.5,
                    1 if inv_amount > 500 else 0,
                    (0 if days_to_due <= 15 else 1 if days_to_due <= 30 else 2 if days_to_due <= 60 else 3),
                ]
            ]
        )

    def predict(self, invoice: Invoice) -> float:
        """Return the probability (0–1) that an invoice will be paid late."""
        self._load()
        if self._model is None:
            return 0.0

        features = self._build_single_feature_vector(invoice)
        if features is None:
            return 0.0

        cust = invoice.customer

        prob = float(self._model.predict_proba(features)[0][1])

        log_prediction(
            self._registry,
            "Invoice",
            invoice.pk,
            prob,
            {
                "invoice_number": invoice.invoice_number,
                "customer": cust.name,
                "amount": float(invoice.total_amount),
            },
        )

        return prob

    def score_all_open_invoices(self) -> list[dict]:
        """Score every open invoice and return results."""
        self._load()
        if self._model is None:
            return []

        invoices = Invoice.objects.filter(
            company=self.company,
            status__in=["sent", "partial"],
            due_date__isnull=False,
        ).select_related("customer")

        results = []
        for inv in invoices:
            try:
                risk = self.predict(inv)
                results.append(
                    {
                        "invoice_id": inv.pk,
                        "invoice_number": inv.invoice_number,
                        "customer": inv.customer.name,
                        "amount": float(inv.total_amount),
                        "due_date": str(inv.due_date),
                        "risk_score": round(risk, 4),
                        "risk_level": ("high" if risk > 0.7 else "medium" if risk > 0.4 else "low"),
                    }
                )
            except Exception as exc:
                logger.exception("Risk scoring failed for invoice %d: %s", inv.pk, exc)

        # Create insight for high-risk invoices
        high_risk = [r for r in results if r["risk_level"] == "high"]
        if high_risk:
            title = f"{len(high_risk)} invoices at high risk of late payment"
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.REVENUE,
                severity=AIInsight.Severity.WARNING,
                title=title,
                description=(
                    "The following invoices have a >70 % probability of being "
                    "paid late: " + ", ".join(f"{r['invoice_number']} ({r['customer']})" for r in high_risk[:10])
                ),
                recommendation=(
                    "Consider sending early reminders or offering early-payment discounts for these customers."
                ),
                action_url="/erp/invoices/",
            )

        return results


# ════════════════════════════════════════════════════════════════════════════
# 2.  Expense Anomaly Detection
# ════════════════════════════════════════════════════════════════════════════


class ExpenseAnomalyDetector:
    """Uses Isolation Forest to flag unusual expenses."""

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, "ML_MIN_TRAINING_SAMPLES", 30)

    def detect(self) -> list[dict]:
        """Scan approved expenses and return anomalies."""
        qs = (
            Expense.objects.filter(
                company=self.company,
            )
            .select_related("category")
            .values(
                "id",
                "expense_number",
                "total_amount",
                "expense_date",
                "category__name",
                "status",
                "employee_id",
            )
        )
        df = pd.DataFrame(list(qs))
        if len(df) < self.min_samples:
            return []

        df["amount"] = df["total_amount"].astype(float)
        df["amount_log"] = np.log1p(df["amount"])
        df["month"] = pd.to_datetime(df["expense_date"]).dt.month
        df["day_of_week"] = pd.to_datetime(df["expense_date"]).dt.dayofweek
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

        le = LabelEncoder()
        df["category_code"] = le.fit_transform(df["category__name"].fillna("Unknown"))

        # Amount relative to category statistics (z-score within category)
        cat_stats = df.groupby("category_code")["amount"].agg(cat_mean="mean", cat_std="std").reset_index()
        cat_stats["cat_std"] = cat_stats["cat_std"].clip(lower=1.0)
        df = df.merge(cat_stats, on="category_code", how="left")
        df["amount_vs_cat_z"] = (df["amount"] - df["cat_mean"]) / df["cat_std"]
        df["amount_vs_cat_ratio"] = df["amount"] / df["cat_mean"].clip(lower=0.01)

        # Employee-level history features
        emp_stats = (
            df.groupby("employee_id")["amount"].agg(emp_mean="mean", emp_std="std", emp_count="count").reset_index()
        )
        emp_stats["emp_std"] = emp_stats["emp_std"].clip(lower=1.0)
        df = df.merge(emp_stats, on="employee_id", how="left")
        df["amount_vs_emp_z"] = (df["amount"] - df["emp_mean"]) / df["emp_std"]

        # Amount percentile (global rank)
        df["amount_percentile"] = df["amount"].rank(pct=True)

        feature_cols = [
            "amount",
            "amount_log",
            "month",
            "day_of_week",
            "is_weekend",
            "category_code",
            "amount_vs_cat_z",
            "amount_vs_cat_ratio",
            "amount_vs_emp_z",
            "emp_count",
            "amount_percentile",
        ]
        features = df[feature_cols].fillna(0).values

        # Dynamic contamination: use IQR-based estimate
        q1 = df["amount"].quantile(0.25)
        q3 = df["amount"].quantile(0.75)
        iqr = q3 - q1
        upper_fence = q3 + 1.5 * iqr
        iqr_outlier_ratio = (df["amount"] > upper_fence).mean()
        contamination = float(np.clip(iqr_outlier_ratio, 0.01, 0.10))

        iso = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=500,
            max_features=0.8,
            max_samples="auto",
        )
        predictions = iso.fit_predict(features)
        scores = iso.decision_function(features)

        df["is_anomaly"] = predictions == -1
        df["anomaly_score"] = scores

        anomalies = df[df["is_anomaly"]].sort_values("anomaly_score")
        results = []
        for _, row in anomalies.iterrows():
            results.append(
                {
                    "expense_id": int(row["id"]),
                    "expense_number": row["expense_number"],
                    "amount": row["amount"],
                    "category": row["category__name"],
                    "date": str(row["expense_date"]),
                    "anomaly_score": round(float(row["anomaly_score"]), 4),
                }
            )

        if results:
            title = f"{len(results)} expense anomalies detected"
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.EXPENSE,
                severity=AIInsight.Severity.WARNING,
                title=title,
                description=(
                    "Isolation Forest flagged the following expenses: "
                    + ", ".join(f"{r['expense_number']} ({r['amount']:.2f})" for r in results[:10])
                ),
                recommendation=("Review flagged expenses for potential errors, policy violations, or fraud."),
                action_url="/erp/expenses/",
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
            delta = (item["date"] - today).days
            if 0 <= delta < periods:
                inflow_series[delta] += item["amount"]

        for item in outflows:
            delta = (item["date"] - today).days
            if 0 <= delta < periods:
                outflow_series[delta] += item["amount"]

        net_series = inflow_series - outflow_series
        cumulative = np.cumsum(net_series)

        # Summary at 30 / 60 / 90 days
        summary = {}
        for horizon in [30, 60, 90]:
            if horizon <= periods:
                summary[f"{horizon}d"] = {
                    "inflows": round(float(inflow_series[:horizon].sum()), 2),
                    "outflows": round(float(outflow_series[:horizon].sum()), 2),
                    "net": round(float(net_series[:horizon].sum()), 2),
                    "cumulative": round(float(cumulative[horizon - 1]), 2),
                }

        # Create insight if negative cumulative
        if cumulative.min() < 0:
            first_neg_day = int(np.argmax(cumulative < 0))
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.CASH_FLOW,
                severity=AIInsight.Severity.CRITICAL,
                title="Projected negative cash flow",
                description=(
                    f"Cash-flow projection shows a negative position starting "
                    f"day {first_neg_day + 1} ({dates[first_neg_day]}). "
                    f"Lowest point: {cumulative.min():,.2f}"
                ),
                recommendation=(
                    "Consider accelerating receivables collection, "
                    "negotiating extended payment terms with suppliers, "
                    "or arranging a credit facility."
                ),
                action_url="/erp/ai/cashflow/",
            )

        return {
            "dates": [d.isoformat() for d in dates],
            "inflows": inflow_series.round(2).tolist(),
            "outflows": outflow_series.round(2).tolist(),
            "net": net_series.round(2).tolist(),
            "cumulative": cumulative.round(2).tolist(),
            "summary": summary,
        }

    def _expected_inflows(self, today, periods):
        """Outstanding invoices expected to be paid by due date."""
        end = today + timedelta(days=periods)
        invoices = Invoice.objects.filter(
            company=self.company,
            status__in=["sent", "partial"],
            due_date__gte=today,
            due_date__lte=end,
        ).values("due_date", "balance_due")

        return [{"date": row["due_date"], "amount": float(row["balance_due"])} for row in invoices]

    def _expected_outflows(self, today, periods):
        """POs and supplier invoices due in the period."""
        end = today + timedelta(days=periods)
        items = []

        # Supplier invoices
        si_qs = SupplierInvoice.objects.filter(
            company=self.company,
            status__in=["pending", "partial"],
            due_date__gte=today,
            due_date__lte=end,
        ).values("due_date", "balance_due")
        for row in si_qs:
            items.append(
                {
                    "date": row["due_date"],
                    "amount": float(row["balance_due"]),
                }
            )

        # Open purchase orders (estimated delivery = today + lead time)
        po_qs = PurchaseOrder.objects.filter(
            company=self.company,
            status__in=["approved", "sent"],
        ).values("po_date", "total_amount")
        for row in po_qs:
            est_date = row["po_date"] + timedelta(days=14)  # default lead
            if today <= est_date <= end:
                items.append(
                    {
                        "date": est_date,
                        "amount": float(row["total_amount"]),
                    }
                )

        return items
