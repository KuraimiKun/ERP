"""
Base utilities shared across AI services.

Provides helpers for model persistence, feature engineering, and logging.
"""

import logging
import joblib
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.utils import timezone

from erp.ai.models import MLModel, PredictionLog, AIInsight

logger = logging.getLogger('erp.ai')


# ── Severity → Notification type mapping ────────────────────────────────
_SEVERITY_TO_NOTIF_TYPE = {
    AIInsight.Severity.CRITICAL: 'error',
    AIInsight.Severity.WARNING:  'warning',
    AIInsight.Severity.INFO:     'info',
}


def get_model_path(company_id: int, model_type: str, version: int) -> Path:
    """Return the filesystem path for a serialised model artefact."""
    directory = Path(settings.ML_MODEL_DIR) / str(company_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f'{model_type}_v{version}.joblib'


def save_model_artefact(ml_model: MLModel, artefact):
    """Persist a sklearn / custom model to disk and update the registry."""
    path = get_model_path(ml_model.company_id, ml_model.model_type,
                          ml_model.version)
    joblib.dump(artefact, path)
    ml_model.artefact_path = str(path.relative_to(settings.ML_MODEL_DIR))
    ml_model.last_trained_at = timezone.now()
    ml_model.save(update_fields=['artefact_path', 'last_trained_at',
                                  'accuracy_score', 'training_samples'])
    logger.info('Saved %s v%d for company %d (samples=%d, score=%.4f)',
                ml_model.model_type, ml_model.version, ml_model.company_id,
                ml_model.training_samples, ml_model.accuracy_score or 0)
    return path


def load_model_artefact(ml_model: MLModel):
    """Load a serialised model artefact from disk."""
    path = Path(settings.ML_MODEL_DIR) / ml_model.artefact_path
    if not path.exists():
        raise FileNotFoundError(f'Model artefact not found: {path}')
    return joblib.load(path)


def get_or_create_registry(company, model_type: str, name: str) -> MLModel:
    """Get the active registry entry or create a new v1."""
    entry = MLModel.objects.filter(
        company=company, model_type=model_type, is_active=True,
    ).order_by('-version').first()
    if entry is None:
        entry = MLModel.objects.create(
            company=company,
            model_type=model_type,
            name=name,
            version=1,
        )
    return entry


def bump_version(ml_model: MLModel) -> MLModel:
    """Create a new version entry for the same model type."""
    new = MLModel.objects.create(
        company=ml_model.company,
        model_type=ml_model.model_type,
        name=ml_model.name,
        version=ml_model.version + 1,
    )
    # Deactivate old version
    MLModel.objects.filter(
        company=ml_model.company, model_type=ml_model.model_type,
    ).exclude(pk=new.pk).update(is_active=False)
    return new


def log_prediction(ml_model: MLModel, entity_type: str, entity_id: int,
                   score: float, details: dict | None = None) -> PredictionLog:
    """Record a prediction for auditing."""
    return PredictionLog.objects.create(
        model=ml_model,
        entity_type=entity_type,
        entity_id=entity_id,
        score=score,
        details=details or {},
    )


# ════════════════════════════════════════════════════════════════════════════
#  Insight deduplication
# ════════════════════════════════════════════════════════════════════════════

def create_or_update_insight(
    company,
    category: str,
    severity: str,
    title: str,
    description: str,
    recommendation: str = '',
    action_url: str = '',
    cooldown_hours: int = 12,
) -> AIInsight:
    """Create a new AIInsight **or** update a recent identical one.

    Prevents duplicate alerts when the same analysis runs multiple times
    within *cooldown_hours*.  The deduplication key is
    (company, category, title, created_at > cutoff, not dismissed).

    If a matching insight already exists within the cooldown window its
    description, recommendation and severity are updated to the latest
    values and its ``created_at`` is bumped so it stays at the top.
    """
    cutoff = timezone.now() - timedelta(hours=cooldown_hours)

    existing = AIInsight.objects.filter(
        company=company,
        category=category,
        title=title,
        is_dismissed=False,
        created_at__gte=cutoff,
    ).order_by('-created_at').first()

    if existing:
        existing.severity = severity
        existing.description = description
        existing.recommendation = recommendation
        existing.action_url = action_url
        # Bump timestamp so it shows as "just now"
        existing.created_at = timezone.now()
        existing.save(update_fields=[
            'severity', 'description', 'recommendation',
            'action_url', 'created_at',
        ])
        return existing

    insight = AIInsight.objects.create(
        company=company,
        category=category,
        severity=severity,
        title=title,
        description=description,
        recommendation=recommendation,
        action_url=action_url,
    )

    # ── Push a Notification to every user in this company ───────────
    _notify_company_users(insight)

    return insight


def _notify_company_users(insight: AIInsight):
    """Create a Notification for every active user linked to the company.

    Imports are deferred to avoid circular imports and to keep the helper
    usable from Celery tasks that run outside a request cycle.
    """
    try:
        from erp.models import Employee, Notification

        notif_type = _SEVERITY_TO_NOTIF_TYPE.get(
            insight.severity, Notification.NotificationType.INFO,
        )

        # Message includes the recommendation when available
        message = insight.description
        if insight.recommendation:
            message += f'\n\nRecommendation: {insight.recommendation}'

        # Target URL: use the insight's action_url, falling back to the
        # AI dashboard so the user can see full details.
        action_url = insight.action_url or '/erp/ai/'

        recipients = (
            Employee.objects.filter(
                company=insight.company,
                user__isnull=False,
                employment_status='active',
            )
            .select_related('user')
        )

        notifications = [
            Notification(
                recipient=emp.user,
                notification_type=notif_type,
                title=f'[AI] {insight.title}',
                message=message,
                action_url=action_url,
            )
            for emp in recipients
        ]

        if notifications:
            Notification.objects.bulk_create(notifications)
            logger.info(
                'AI notification sent to %d users for insight "%s"',
                len(notifications), insight.title,
            )
    except Exception as exc:
        # Never let a notification failure break the AI pipeline
        logger.exception('Failed to send AI notifications: %s', exc)
