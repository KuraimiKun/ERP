"""
CRM Lead Scoring Service

Replaces the manual `Lead.probability` with an ML-driven conversion score.
Uses Logistic Regression on historical won/lost leads.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from django.conf import settings
from django.db.models import Min, Max
from django.utils import timezone

from erp.models import Lead, LeadActivity
from erp.ai.models import MLModel, AIInsight
from .base import (
    get_or_create_registry,
    save_model_artefact,
    load_model_artefact,
    log_prediction,
    create_or_update_insight,
    evaluate_classifier,
    shuffle_label_auc,
)

logger = logging.getLogger("erp.ai.crm")

HOT_THRESHOLD = getattr(settings, "ML_LEAD_HOT_THRESHOLD", 0.70)


class LeadScorer:
    """ML-driven lead conversion scoring."""

    FEATURE_COLS = [
        "estimated_value",
        "value_log",
        "activity_count",
        "call_count",
        "email_count",
        "meeting_count",
        "note_count",
        "source_code",
        "has_company",
        "has_email",
        "has_phone",
        "avg_days_between_activities",
        "last_activity_days_ago",
        "source_conversion_rate",
    ]

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, "ML_MIN_TRAINING_SAMPLES", 30)
        self._model = None
        self._registry = None
        self._source_map = {}
        self._source_conv_rates = {}

    # ── Dataset ─────────────────────────────────────────────────────────

    def _build_dataset(self) -> pd.DataFrame:
        """Build labelled dataset from historical won/lost leads."""
        leads = Lead.objects.filter(
            company=self.company,
            status__in=["won", "lost"],
        ).values(
            "id",
            "status",
            "source",
            "estimated_value",
            "created_at",
            "conversion_date",
            "company_name",
            "email",
            "phone",
        )
        df = pd.DataFrame(list(leads))
        if df.empty or len(df) < self.min_samples:
            return pd.DataFrame()

        # Label
        df["label"] = (df["status"] == "won").astype(int)

        # Features
        df["estimated_value"] = df["estimated_value"].fillna(0).astype(float)
        # Use conversion_date (or created_at + 30 for lost leads) as the
        # reference point so temporal features reflect lead lifetime, not
        # absolute staleness.
        df["_ref_date"] = pd.to_datetime(
            df["conversion_date"],
            utc=True,
            errors="coerce",
        )
        df["_created"] = pd.to_datetime(df["created_at"], utc=True)
        df.loc[df["_ref_date"].isna(), "_ref_date"] = df.loc[df["_ref_date"].isna(), "_created"] + pd.Timedelta(days=30)

        # Activity counts — only count activities that occurred at or
        # before the lead's reference date (outcome timestamp) so features
        # don't leak post-conversion activity.
        ref_dates = {
            row["id"]: row["_ref_date"]
            for _, row in df[["id", "_ref_date"]].iterrows()
        }
        ref_ids = list(ref_dates.keys())

        all_activities = list(
            LeadActivity.objects.filter(
                lead__company=self.company,
                lead_id__in=ref_ids,
            ).values("lead_id", "activity_type", "activity_date")
        )
        # Pre-convert to pandas Timestamp (UTC) once.
        acts_df = pd.DataFrame(all_activities)
        if not acts_df.empty:
            acts_df["activity_date"] = pd.to_datetime(
                acts_df["activity_date"], utc=True, errors="coerce"
            )
            ref_series = pd.Series(ref_dates, name="_ref_date")
            ref_series.index.name = "lead_id"
            acts_df = acts_df.merge(ref_series, left_on="lead_id", right_index=True)
            acts_df = acts_df[acts_df["activity_date"] <= acts_df["_ref_date"]]

        activity_counts = (
            acts_df.groupby("lead_id").size().to_dict() if not acts_df.empty else {}
        )
        df["activity_count"] = df["id"].map(activity_counts).fillna(0).astype(int)

        # Activity type breakdowns (from the same leak-safe filtered set)
        for atype in ["call", "email", "meeting", "note"]:
            if not acts_df.empty:
                type_counts = (
                    acts_df[acts_df["activity_type"] == atype]
                    .groupby("lead_id")
                    .size()
                    .to_dict()
                )
            else:
                type_counts = {}
            df[f"{atype}_count"] = df["id"].map(type_counts).fillna(0).astype(int)

        # Engagement velocity: avg days between activities (leak-safe)
        velocity_map = {}
        recency_map = {}
        if not acts_df.empty:
            grouped = acts_df.groupby("lead_id")["activity_date"].agg(
                first_act="min", last_act="max", act_count="count"
            )
            for lead_id, row in grouped.iterrows():
                if row["act_count"] > 1:
                    span = (row["last_act"] - row["first_act"]).days
                    velocity_map[lead_id] = span / max(row["act_count"] - 1, 1)
                else:
                    velocity_map[lead_id] = 0
                recency_map[lead_id] = row["last_act"]

        df["avg_days_between_activities"] = df["id"].map(velocity_map).fillna(0)
        # Days from last activity to reference date (lead close)
        df["_last_act"] = df["id"].map(recency_map)
        df["_last_act"] = pd.to_datetime(df["_last_act"], utc=True, errors="coerce")
        df["last_activity_days_ago"] = (df["_ref_date"] - df["_last_act"]).dt.days.fillna(999).clip(lower=0)

        # Log-transformed value
        df["value_log"] = np.log1p(df["estimated_value"])

        # Source encoding
        sources = sorted(df["source"].dropna().unique().tolist())
        self._source_map = {s: i for i, s in enumerate(sources)}
        df["source_code"] = df["source"].map(self._source_map).fillna(-1).astype(int)

        df["has_company"] = (df["company_name"].fillna("").str.len() > 0).astype(int)
        df["has_email"] = (df["email"].fillna("").str.len() > 0).astype(int)
        df["has_phone"] = (df["phone"].fillna("").str.len() > 0).astype(int)

        # Source conversion rate — **true** leave-one-out (previously the
        # full-group mean was used, which includes the current row's label
        # and therefore leaks).
        source_stats = df.groupby("source")["label"].agg(src_total="count", src_won="sum").reset_index()
        df = df.merge(
            source_stats,
            on="source",
            how="left",
        )
        df["source_conversion_rate"] = (
            (df["src_won"] - df["label"]) / (df["src_total"] - 1).clip(lower=1)
        ).fillna(0).clip(0, 1)
        df = df.drop(columns=["src_total", "src_won"])

        return df

    # ── Training ────────────────────────────────────────────────────────

    def train(self, shuffle_labels: bool = False) -> dict:
        """Train the lead scoring model."""
        df = self._build_dataset()
        if df.empty:
            logger.info("Insufficient lead data for scoring model (company %d)", self.company.pk)
            return {"status": "skipped", "reason": "insufficient_data"}

        X = df[self.FEATURE_COLS].values
        y = df["label"].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Sample-weight function (closed over class imbalance of y_tr)
        def _weights(y_tr: np.ndarray) -> np.ndarray:
            pos = y_tr.mean()
            return np.where(
                y_tr == 1,
                1.0 / max(pos, 0.01),
                1.0 / max(1 - pos, 0.01),
            )

        clf = GradientBoostingClassifier(
            n_estimators=400,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=10,
            random_state=42,
            max_features="sqrt",
            validation_fraction=0.1,
            n_iter_no_change=30,
        )

        # Shuffle-label sanity check run — return without persisting.
        if shuffle_labels:
            shuffled = shuffle_label_auc(clf, X_scaled, y, n_repeats=5, sample_weight_fn=_weights)
            return {
                "status": "shuffle_check",
                "shuffled_auc": shuffled,
                "samples": len(df),
                "note": "AUC > 0.55 with shuffled labels indicates target leakage.",
            }

        # Stratified K-fold evaluation with baseline.
        cv_metrics = evaluate_classifier(clf, X_scaled, y, sample_weight_fn=_weights)
        shuffle_auc = shuffle_label_auc(clf, X_scaled, y, sample_weight_fn=_weights)

        # Final refit on full data for production use.
        clf.fit(X_scaled, y, sample_weight=_weights(y))

        auc = cv_metrics.get("auc_mean") or 0.0

        registry = get_or_create_registry(
            self.company,
            MLModel.ModelType.LEAD_SCORING,
            "Lead Scoring Model",
        )
        registry.training_samples = len(df)
        registry.accuracy_score = auc
        registry.parameters = {
            "feature_cols": self.FEATURE_COLS,
            "source_map": self._source_map,
            "cv_metrics": cv_metrics,
            "shuffled_label_auc": shuffle_auc,
        }

        # Build source conversion rate lookup for prediction
        source_conv_rates = dict(df.groupby("source")["label"].mean())

        save_model_artefact(
            registry,
            {
                "classifier": clf,
                "scaler": scaler,
                "source_map": self._source_map,
                "source_conv_rates": source_conv_rates,
                "feature_cols": self.FEATURE_COLS,
            },
        )

        self._model = clf
        self._scaler = scaler
        self._registry = registry
        self._source_conv_rates = source_conv_rates

        logger.info("Lead scoring model trained: AUC=%.4f samples=%d", auc, len(df))
        return {
            "status": "trained",
            "auc": round(auc, 4),
            "samples": len(df),
            "cv_metrics": cv_metrics,
            "shuffled_label_auc": shuffle_auc,
        }

    # ── Prediction ──────────────────────────────────────────────────────

    def _load(self):
        if self._model is not None:
            return
        self._registry = get_or_create_registry(
            self.company,
            MLModel.ModelType.LEAD_SCORING,
            "Lead Scoring Model",
        )
        if not self._registry.artefact_path:
            self.train()
            return
        artefact = load_model_artefact(self._registry)
        self._model = artefact["classifier"]
        self._scaler = artefact["scaler"]
        self._source_map = artefact.get("source_map", {})
        self._source_conv_rates = artefact.get("source_conv_rates", {})

    def _build_single_feature_vector(self, lead: Lead) -> np.ndarray | None:
        """Build the feature vector for a single lead.

        Returns a (1, n_features) numpy array matching FEATURE_COLS order,
        or None if features cannot be built.
        Used by both score_lead() and the XAI explainability service.
        """
        now = timezone.now()

        activities = LeadActivity.objects.filter(lead=lead)
        activity_count = activities.count()
        call_count = activities.filter(activity_type="call").count()
        email_count = activities.filter(activity_type="email").count()
        meeting_count = activities.filter(activity_type="meeting").count()
        note_count = activities.filter(activity_type="note").count()

        act_dates = activities.aggregate(
            first_act=Min("activity_date"),
            last_act=Max("activity_date"),
        )
        avg_days_between = 0
        last_act_days = 999
        if act_dates["first_act"] and act_dates["last_act"] and activity_count > 1:
            span = (act_dates["last_act"] - act_dates["first_act"]).days
            avg_days_between = span / max(activity_count - 1, 1)
        if act_dates["last_act"]:
            last_act_days = (now - act_dates["last_act"]).days

        source_cr = self._source_conv_rates.get(lead.source, 0)

        return np.array(
            [
                [
                    float(lead.estimated_value or 0),
                    np.log1p(float(lead.estimated_value or 0)),
                    activity_count,
                    call_count,
                    email_count,
                    meeting_count,
                    note_count,
                    self._source_map.get(lead.source, -1),
                    1 if lead.company_name else 0,
                    1 if lead.email else 0,
                    1 if lead.phone or lead.mobile else 0,
                    avg_days_between,
                    last_act_days,
                    source_cr,
                ]
            ]
        )

    def score_lead(self, lead: Lead) -> float:
        """Return conversion probability 0–1 for a lead."""
        self._load()
        if self._model is None:
            return lead.probability / 100.0 if lead.probability else 0.1

        features = self._build_single_feature_vector(lead)
        if features is None:
            return lead.probability / 100.0 if lead.probability else 0.1

        features_scaled = self._scaler.transform(features)
        prob = float(self._model.predict_proba(features_scaled)[0][1])

        log_prediction(
            self._registry,
            "Lead",
            lead.pk,
            prob,
            {
                "lead_number": lead.lead_number,
                "name": lead.full_name,
                "source": lead.source,
            },
        )

        return prob

    def score_all_active_leads(self) -> list[dict]:
        """Score every active (non-closed) lead."""
        self._load()
        if self._model is None:
            return []

        leads = Lead.objects.filter(
            company=self.company,
        ).exclude(status__in=["won", "lost", "inactive"])

        results = []
        hot_leads = []
        for lead in leads:
            try:
                score = self.score_lead(lead)
                level = "hot" if score >= HOT_THRESHOLD else "warm" if score >= 0.4 else "cold"
                result = {
                    "lead_id": lead.pk,
                    "lead_number": lead.lead_number,
                    "name": lead.full_name,
                    "score": round(score, 4),
                    "level": level,
                    "current_status": lead.status,
                    "estimated_value": float(lead.estimated_value or 0),
                }
                results.append(result)
                if level == "hot":
                    hot_leads.append(result)

                # Optionally update the probability field
                new_prob = int(score * 100)
                if new_prob != lead.probability:
                    Lead.objects.filter(pk=lead.pk).update(probability=new_prob)

            except Exception as exc:
                logger.exception("Lead scoring failed for %d: %s", lead.pk, exc)

        if hot_leads:
            title = f"{len(hot_leads)} hot leads identified"
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.CRM,
                severity=AIInsight.Severity.INFO,
                title=title,
                description=(
                    "ML scoring detected high-conversion leads: "
                    + ", ".join(f"{l['lead_number']} – {l['name']} ({l['score']:.0%})" for l in hot_leads[:10])
                ),
                recommendation=("Prioritise follow-up on these leads to maximise conversion rate."),
                action_url="/erp/leads/",
            )

        return results
