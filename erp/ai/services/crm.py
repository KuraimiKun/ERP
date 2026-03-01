"""
CRM Lead Scoring Service

Replaces the manual `Lead.probability` with an ML-driven conversion score.
Uses Logistic Regression on historical won/lost leads.
"""

import logging
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from django.conf import settings
from django.db.models import Count, Avg
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
        'estimated_value', 'days_since_created', 'activity_count',
        'source_code', 'has_company', 'has_email', 'has_phone',
    ]

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, 'ML_MIN_TRAINING_SAMPLES', 30)
        self._model = None
        self._registry = None
        self._source_map = {}

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
        now = timezone.now()
        df['days_since_created'] = (
            now - pd.to_datetime(df['created_at'], utc=True)
        ).dt.days

        # Activity counts
        activity_counts = dict(
            LeadActivity.objects.filter(
                lead__company=self.company,
                lead__status__in=['won', 'lost'],
            ).values('lead_id').annotate(cnt=Count('id')).values_list(
                'lead_id', 'cnt')
        )
        df['activity_count'] = df['id'].map(activity_counts).fillna(0).astype(int)

        # Source encoding
        sources = sorted(df['source'].dropna().unique().tolist())
        self._source_map = {s: i for i, s in enumerate(sources)}
        df['source_code'] = df['source'].map(self._source_map).fillna(-1).astype(int)

        df['has_company'] = (df['company_name'].fillna('').str.len() > 0).astype(int)
        df['has_email'] = (df['email'].fillna('').str.len() > 0).astype(int)
        df['has_phone'] = (df['phone'].fillna('').str.len() > 0).astype(int)

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

        clf = LogisticRegression(max_iter=1000, random_state=42, C=1.0)
        clf.fit(X_train, y_train)

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
        save_model_artefact(registry, {
            'classifier': clf,
            'scaler': scaler,
            'source_map': self._source_map,
            'feature_cols': self.FEATURE_COLS,
        })

        self._model = clf
        self._scaler = scaler
        self._registry = registry

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

    def score_lead(self, lead: Lead) -> float:
        """Return conversion probability 0–1 for a lead."""
        self._load()
        if self._model is None:
            return lead.probability / 100.0 if lead.probability else 0.1

        activity_count = LeadActivity.objects.filter(lead=lead).count()
        now = timezone.now()
        days = (now - lead.created_at).days if lead.created_at else 0

        features = np.array([[
            float(lead.estimated_value or 0),
            days,
            activity_count,
            self._source_map.get(lead.source, -1),
            1 if lead.company_name else 0,
            1 if lead.email else 0,
            1 if lead.phone or lead.mobile else 0,
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
