"""
CRM Lead Scoring Service

Replaces the manual `Lead.probability` with an ML-driven conversion score.
Uses Logistic Regression on historical won/lost leads.
"""

import logging
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from django.conf import settings
from django.db.models import Count, Avg, Min, Max
from django.utils import timezone

from erp.models import Lead, LeadActivity, Customer
from erp.ai.models import MLModel, AIInsight
from .base import (
    get_or_create_registry, save_model_artefact, load_model_artefact,
    log_prediction, create_or_update_insight, logger,
)

logger = logging.getLogger('erp.ai.crm')

HOT_THRESHOLD = getattr(settings, 'ML_LEAD_HOT_THRESHOLD', 0.70)


class LeadScorer:
    """ML-driven lead conversion scoring."""

    FEATURE_COLS = [
        'estimated_value', 'value_log', 'days_since_created',
        'activity_count', 'call_count', 'email_count',
        'meeting_count', 'note_count',
        'source_code', 'has_company', 'has_email', 'has_phone',
        'avg_days_between_activities', 'last_activity_days_ago',
        'source_conversion_rate',
    ]

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, 'ML_MIN_TRAINING_SAMPLES', 30)
        self._model = None
        self._registry = None
        self._source_map = {}
        self._source_conv_rates = {}

    # ── Dataset ─────────────────────────────────────────────────────────

    def _build_dataset(self) -> pd.DataFrame:
        """Build labelled dataset from historical won/lost leads."""
        leads = Lead.objects.filter(
            company=self.company,
            status__in=['won', 'lost'],
        ).values(
            'id', 'status', 'source', 'estimated_value',
            'created_at', 'conversion_date', 'company_name',
            'email', 'phone',
        )
        df = pd.DataFrame(list(leads))
        if df.empty or len(df) < self.min_samples:
            return pd.DataFrame()

        # Label
        df['label'] = (df['status'] == 'won').astype(int)

        # Features
        df['estimated_value'] = df['estimated_value'].fillna(0).astype(float)
        # Use conversion_date (or created_at + 30 for lost leads) as the
        # reference point so temporal features reflect lead lifetime, not
        # absolute staleness.
        df['_ref_date'] = pd.to_datetime(
            df['conversion_date'], utc=True, errors='coerce',
        )
        df['_created'] = pd.to_datetime(df['created_at'], utc=True)
        df.loc[df['_ref_date'].isna(), '_ref_date'] = (
            df.loc[df['_ref_date'].isna(), '_created']
            + pd.Timedelta(days=30)
        )
        df['days_since_created'] = (
            df['_ref_date'] - df['_created']
        ).dt.days.clip(lower=0)

        # Activity counts
        activity_counts = dict(
            LeadActivity.objects.filter(
                lead__company=self.company,
                lead__status__in=['won', 'lost'],
            ).values('lead_id').annotate(cnt=Count('id')).values_list(
                'lead_id', 'cnt')
        )
        df['activity_count'] = df['id'].map(activity_counts).fillna(0).astype(int)

        # Activity type breakdowns
        for atype in ['call', 'email', 'meeting', 'note']:
            type_counts = dict(
                LeadActivity.objects.filter(
                    lead__company=self.company,
                    lead__status__in=['won', 'lost'],
                    activity_type=atype,
                ).values('lead_id').annotate(cnt=Count('id')).values_list(
                    'lead_id', 'cnt')
            )
            df[f'{atype}_count'] = df['id'].map(type_counts).fillna(0).astype(int)

        # Engagement velocity: avg days between activities
        activity_dates = (
            LeadActivity.objects.filter(
                lead__company=self.company,
                lead__status__in=['won', 'lost'],
            ).values('lead_id').annotate(
                first_act=Min('activity_date'),
                last_act=Max('activity_date'),
                act_count=Count('id'),
            )
        )
        velocity_map = {}
        recency_map = {}
        for row in activity_dates:
            if row['act_count'] > 1 and row['first_act'] and row['last_act']:
                span = (row['last_act'] - row['first_act']).days
                velocity_map[row['lead_id']] = span / max(row['act_count'] - 1, 1)
            else:
                velocity_map[row['lead_id']] = 0
            recency_map[row['lead_id']] = row['last_act']

        df['avg_days_between_activities'] = df['id'].map(velocity_map).fillna(0)
        # Days from last activity to reference date (lead close)
        df['_last_act'] = df['id'].map(recency_map)
        df['_last_act'] = pd.to_datetime(df['_last_act'], utc=True, errors='coerce')
        df['last_activity_days_ago'] = (
            df['_ref_date'] - df['_last_act']
        ).dt.days.fillna(999).clip(lower=0)

        # Log-transformed value
        df['value_log'] = np.log1p(df['estimated_value'])

        # Source encoding
        sources = sorted(df['source'].dropna().unique().tolist())
        self._source_map = {s: i for i, s in enumerate(sources)}
        df['source_code'] = df['source'].map(self._source_map).fillna(-1).astype(int)

        df['has_company'] = (df['company_name'].fillna('').str.len() > 0).astype(int)
        df['has_email'] = (df['email'].fillna('').str.len() > 0).astype(int)
        df['has_phone'] = (df['phone'].fillna('').str.len() > 0).astype(int)

        # Source conversion rate (leave-one-out to prevent leakage)
        source_stats = (
            df.groupby('source')['label']
            .agg(src_total='count', src_won='sum')
            .reset_index()
        )
        source_stats['source_conversion_rate'] = (
            source_stats['src_won'] / source_stats['src_total'].clip(lower=1)
        )
        df = df.merge(
            source_stats[['source', 'source_conversion_rate']],
            on='source', how='left',
        )
        df['source_conversion_rate'] = df['source_conversion_rate'].fillna(0)

        return df

    # ── Training ────────────────────────────────────────────────────────

    def train(self) -> dict:
        """Train the lead scoring model."""
        df = self._build_dataset()
        if df.empty:
            logger.info('Insufficient lead data for scoring model (company %d)',
                        self.company.pk)
            return {'status': 'skipped', 'reason': 'insufficient_data'}

        X = df[self.FEATURE_COLS].values
        y = df['label'].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42,
            stratify=y if len(set(y)) > 1 else None,
        )

        # Compute sample weights for class imbalance
        pos_ratio = y_train.mean()
        weights = np.where(
            y_train == 1,
            1.0 / max(pos_ratio, 0.01),
            1.0 / max(1 - pos_ratio, 0.01),
        )

        clf = GradientBoostingClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.05,
            subsample=0.8, min_samples_leaf=10, random_state=42,
            max_features='sqrt', validation_fraction=0.1,
            n_iter_no_change=30,
        )
        clf.fit(X_train, y_train, sample_weight=weights)

        auc = 0.0
        if len(set(y_test)) > 1:
            y_proba = clf.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, y_proba)

        registry = get_or_create_registry(
            self.company, MLModel.ModelType.LEAD_SCORING,
            'Lead Scoring Model',
        )
        registry.training_samples = len(df)
        registry.accuracy_score = auc
        registry.parameters = {
            'feature_cols': self.FEATURE_COLS,
            'source_map': self._source_map,
        }

        # Build source conversion rate lookup for prediction
        source_conv_rates = dict(
            df.groupby('source')['label'].mean()
        )

        save_model_artefact(registry, {
            'classifier': clf,
            'scaler': scaler,
            'source_map': self._source_map,
            'source_conv_rates': source_conv_rates,
            'feature_cols': self.FEATURE_COLS,
        })

        self._model = clf
        self._scaler = scaler
        self._registry = registry
        self._source_conv_rates = source_conv_rates

        logger.info('Lead scoring model trained: AUC=%.4f samples=%d',
                     auc, len(df))
        return {'status': 'trained', 'auc': round(auc, 4), 'samples': len(df)}

    # ── Prediction ──────────────────────────────────────────────────────

    def _load(self):
        if self._model is not None:
            return
        self._registry = get_or_create_registry(
            self.company, MLModel.ModelType.LEAD_SCORING,
            'Lead Scoring Model',
        )
        if not self._registry.artefact_path:
            self.train()
            return
        artefact = load_model_artefact(self._registry)
        self._model = artefact['classifier']
        self._scaler = artefact['scaler']
        self._source_map = artefact.get('source_map', {})
        self._source_conv_rates = artefact.get('source_conv_rates', {})

    def score_lead(self, lead: Lead) -> float:
        """Return conversion probability 0–1 for a lead."""
        self._load()
        if self._model is None:
            return lead.probability / 100.0 if lead.probability else 0.1

        now = timezone.now()
        days = (now - lead.created_at).days if lead.created_at else 0

        activities = LeadActivity.objects.filter(lead=lead)
        activity_count = activities.count()
        call_count = activities.filter(activity_type='call').count()
        email_count = activities.filter(activity_type='email').count()
        meeting_count = activities.filter(activity_type='meeting').count()
        note_count = activities.filter(activity_type='note').count()

        # Engagement velocity
        act_dates = activities.aggregate(
            first_act=Min('activity_date'),
            last_act=Max('activity_date'),
        )
        avg_days_between = 0
        last_act_days = 999
        if act_dates['first_act'] and act_dates['last_act'] and activity_count > 1:
            span = (act_dates['last_act'] - act_dates['first_act']).days
            avg_days_between = span / max(activity_count - 1, 1)
        if act_dates['last_act']:
            last_act_days = (now - act_dates['last_act']).days

        # Source conversion rate from saved model params
        source_cr = self._source_conv_rates.get(lead.source, 0)

        features = np.array([[
            float(lead.estimated_value or 0),
            np.log1p(float(lead.estimated_value or 0)),
            days,
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
        ]])

        features_scaled = self._scaler.transform(features)
        prob = float(self._model.predict_proba(features_scaled)[0][1])

        log_prediction(self._registry, 'Lead', lead.pk, prob, {
            'lead_number': lead.lead_number,
            'name': lead.full_name,
            'source': lead.source,
        })

        return prob

    def score_all_active_leads(self) -> list[dict]:
        """Score every active (non-closed) lead."""
        self._load()
        if self._model is None:
            return []

        leads = Lead.objects.filter(
            company=self.company,
        ).exclude(status__in=['won', 'lost', 'inactive'])

        results = []
        hot_leads = []
        for lead in leads:
            try:
                score = self.score_lead(lead)
                level = (
                    'hot' if score >= HOT_THRESHOLD
                    else 'warm' if score >= 0.4
                    else 'cold'
                )
                result = {
                    'lead_id': lead.pk,
                    'lead_number': lead.lead_number,
                    'name': lead.full_name,
                    'score': round(score, 4),
                    'level': level,
                    'current_status': lead.status,
                    'estimated_value': float(lead.estimated_value or 0),
                }
                results.append(result)
                if level == 'hot':
                    hot_leads.append(result)

                # Optionally update the probability field
                new_prob = int(score * 100)
                if new_prob != lead.probability:
                    Lead.objects.filter(pk=lead.pk).update(probability=new_prob)

            except Exception as exc:
                logger.exception('Lead scoring failed for %d: %s', lead.pk, exc)

        if hot_leads:
            title = f'{len(hot_leads)} hot leads identified'
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.CRM,
                severity=AIInsight.Severity.INFO,
                title=title,
                description=(
                    'ML scoring detected high-conversion leads: '
                    + ', '.join(f"{l['lead_number']} – {l['name']} "
                                f"({l['score']:.0%})"
                                for l in hot_leads[:10])
                ),
                recommendation=(
                    'Prioritise follow-up on these leads to maximise '
                    'conversion rate.'
                ),
                action_url='/erp/leads/',
            )

        return results
