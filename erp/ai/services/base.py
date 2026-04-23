"""
Base utilities shared across AI services.

Provides helpers for model persistence, feature engineering, and logging.
"""

import hashlib
import logging
import joblib
from datetime import timedelta
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold

from django.conf import settings
from django.utils import timezone

from erp.ai.models import MLModel, PredictionLog, AIInsight

logger = logging.getLogger("erp.ai")


# ── Severity → Notification type mapping ────────────────────────────────
_SEVERITY_TO_NOTIF_TYPE = {
    AIInsight.Severity.CRITICAL: "error",
    AIInsight.Severity.WARNING: "warning",
    AIInsight.Severity.INFO: "info",
}


def get_model_path(company_id: int, model_type: str, version: int) -> Path:
    """Return the filesystem path for a serialised model artefact."""
    directory = Path(settings.ML_MODEL_DIR) / str(company_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{model_type}_v{version}.joblib"


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def save_model_artefact(ml_model: MLModel, artefact):
    """Persist a sklearn / custom model to disk and update the registry."""
    path = get_model_path(ml_model.company_id, ml_model.model_type, ml_model.version)
    joblib.dump(artefact, path)
    ml_model.artefact_path = str(path.relative_to(settings.ML_MODEL_DIR))
    ml_model.artefact_sha256 = _sha256(path)
    ml_model.last_trained_at = timezone.now()
    ml_model.save(
        update_fields=["artefact_path", "artefact_sha256", "last_trained_at", "accuracy_score", "training_samples"]
    )
    logger.info(
        "Saved %s v%d for company %d (samples=%d, score=%.4f)",
        ml_model.model_type,
        ml_model.version,
        ml_model.company_id,
        ml_model.training_samples,
        ml_model.accuracy_score or 0,
    )
    return path


def load_model_artefact(ml_model: MLModel):
    """Load a serialised model artefact from disk.

    Security hardening:
    - Rejects artefact_path values containing '..' to prevent path traversal.
    - Validates that the resolved path is inside ML_MODEL_DIR.
    - Verifies the SHA-256 checksum (when stored) to detect tampering.
    """
    raw_path = ml_model.artefact_path
    if ".." in raw_path:
        raise ValueError(f"Refusing to load artefact with path-traversal segments: {raw_path}")

    base = Path(settings.ML_MODEL_DIR).resolve()
    path = (base / raw_path).resolve()

    # Ensure the resolved path is still within ML_MODEL_DIR
    if not str(path).startswith(str(base)):
        raise ValueError(f"Artefact path resolves outside ML_MODEL_DIR: {path}")

    if not path.exists():
        raise FileNotFoundError(f"Model artefact not found: {path}")

    # Verify checksum when available
    expected_hash = getattr(ml_model, "artefact_sha256", "") or ""
    if expected_hash:
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"Checksum mismatch for {path} – artefact may have been "
                f"tampered with (expected {expected_hash[:16]}…, "
                f"got {actual_hash[:16]}…)"
            )

    return joblib.load(path)


def get_or_create_registry(company, model_type: str, name: str) -> MLModel:
    """Get the active registry entry or create a new v1."""
    entry = (
        MLModel.objects.filter(
            company=company,
            model_type=model_type,
            is_active=True,
        )
        .order_by("-version")
        .first()
    )
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
        company=ml_model.company,
        model_type=ml_model.model_type,
    ).exclude(pk=new.pk).update(is_active=False)
    return new


def evaluate_classifier(
    estimator,
    X: np.ndarray,
    y: np.ndarray,
    *,
    n_splits: int = 5,
    sample_weight_fn=None,
    top_k_fraction: float = 0.10,
    random_state: int = 42,
) -> dict:
    """Stratified K-fold CV evaluation with rich metrics.

    Returns a dict with mean ± std of AUC, PR-AUC, F1, Brier score, plus
    precision@top-K and a naive ``DummyClassifier`` baseline AUC so that
    the headline score can be put in context.

    The ``estimator`` must be an unfitted sklearn-compatible classifier.
    It is cloned on each fold so the caller can refit it on the full
    dataset afterwards if desired.  ``sample_weight_fn(y_train)`` may
    return a per-sample weight vector to pass to ``.fit``.

    Gracefully falls back to a single 80/20 split when there are too few
    samples / classes for meaningful K-fold.
    """
    X = np.asarray(X)
    y = np.asarray(y)
    classes = np.unique(y)
    metrics: dict = {
        "n_samples": int(len(y)),
        "n_splits": 0,
        "positive_rate": float(np.mean(y)) if len(y) else 0.0,
    }

    if len(classes) < 2 or len(y) < max(n_splits * 2, 10):
        # Not enough data / class diversity for stratified K-fold.
        metrics["cv_status"] = "insufficient_data_for_cv"
        return metrics

    # Cap K so every fold has at least one positive.
    min_class = int(np.min(np.bincount(y.astype(int))))
    k = max(2, min(n_splits, min_class))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=random_state)

    auc_scores, pr_auc_scores, f1_scores, brier_scores, top_k_prec = [], [], [], [], []
    dummy_auc_scores = []

    for train_idx, test_idx in skf.split(X, y):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        if len(np.unique(y_te)) < 2 or len(np.unique(y_tr)) < 2:
            continue

        est = clone(estimator)
        fit_kwargs = {}
        if sample_weight_fn is not None:
            fit_kwargs["sample_weight"] = sample_weight_fn(y_tr)
        try:
            est.fit(X_tr, y_tr, **fit_kwargs)
        except TypeError:
            # Estimator does not support sample_weight kwarg
            est.fit(X_tr, y_tr)

        proba = est.predict_proba(X_te)[:, 1]
        preds = (proba >= 0.5).astype(int)

        auc_scores.append(roc_auc_score(y_te, proba))
        pr_auc_scores.append(average_precision_score(y_te, proba))
        f1_scores.append(f1_score(y_te, preds, zero_division=0))
        brier_scores.append(brier_score_loss(y_te, proba))

        # Precision @ top-K: fraction of positives in the top-K ranked rows.
        k_rows = max(1, int(np.ceil(len(y_te) * top_k_fraction)))
        order = np.argsort(-proba)[:k_rows]
        top_k_prec.append(float(np.mean(y_te[order])))

        # Baseline: stratified dummy classifier on the same fold.
        dummy = DummyClassifier(strategy="stratified", random_state=random_state)
        dummy.fit(X_tr, y_tr)
        dummy_proba = dummy.predict_proba(X_te)[:, 1]
        try:
            dummy_auc_scores.append(roc_auc_score(y_te, dummy_proba))
        except ValueError:
            dummy_auc_scores.append(0.5)

    def _mean_std(xs):
        if not xs:
            return None, None
        return float(np.mean(xs)), float(np.std(xs))

    auc_mean, auc_std = _mean_std(auc_scores)
    pr_auc_mean, pr_auc_std = _mean_std(pr_auc_scores)
    f1_mean, f1_std = _mean_std(f1_scores)
    brier_mean, brier_std = _mean_std(brier_scores)
    topk_mean, _ = _mean_std(top_k_prec)
    dummy_auc_mean, _ = _mean_std(dummy_auc_scores)

    metrics.update(
        {
            "cv_status": "ok",
            "n_splits": k,
            "auc_mean": auc_mean,
            "auc_std": auc_std,
            "pr_auc_mean": pr_auc_mean,
            "pr_auc_std": pr_auc_std,
            "f1_mean": f1_mean,
            "f1_std": f1_std,
            "brier_mean": brier_mean,
            "brier_std": brier_std,
            "precision_at_top_{}pct".format(int(top_k_fraction * 100)): topk_mean,
            "dummy_auc_mean": dummy_auc_mean,
            "n_positives": int(np.sum(y == 1)),
            "n_negatives": int(np.sum(y == 0)),
        }
    )
    return metrics


def shuffle_label_auc(
    estimator,
    X: np.ndarray,
    y: np.ndarray,
    *,
    n_repeats: int = 3,
    sample_weight_fn=None,
    random_state: int = 42,
) -> float | None:
    """Train on randomly shuffled labels and report the mean AUC.

    This is a **leakage sanity check**: if a model can still achieve an
    AUC noticeably above 0.5 on shuffled labels, the feature set is
    inadvertently encoding the target.  Returns None when the input is
    too small or single-class to evaluate.
    """
    X = np.asarray(X)
    y = np.asarray(y)
    if len(np.unique(y)) < 2 or len(y) < 20:
        return None

    rng = np.random.default_rng(random_state)
    from sklearn.model_selection import train_test_split

    aucs = []
    for i in range(n_repeats):
        y_shuf = y.copy()
        rng.shuffle(y_shuf)
        try:
            X_tr, X_te, y_tr, y_te = train_test_split(
                X, y_shuf, test_size=0.2, stratify=y_shuf, random_state=random_state + i
            )
        except ValueError:
            continue
        if len(np.unique(y_te)) < 2:
            continue
        est = clone(estimator)
        fit_kwargs = {}
        if sample_weight_fn is not None:
            fit_kwargs["sample_weight"] = sample_weight_fn(y_tr)
        try:
            est.fit(X_tr, y_tr, **fit_kwargs)
        except TypeError:
            est.fit(X_tr, y_tr)
        proba = est.predict_proba(X_te)[:, 1]
        aucs.append(roc_auc_score(y_te, proba))

    if not aucs:
        return None
    return float(np.mean(aucs))


def log_prediction(
    ml_model: MLModel, entity_type: str, entity_id: int, score: float, details: dict | None = None
) -> PredictionLog:
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
    recommendation: str = "",
    action_url: str = "",
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

    existing = (
        AIInsight.objects.filter(
            company=company,
            category=category,
            title=title,
            is_dismissed=False,
            created_at__gte=cutoff,
        )
        .order_by("-created_at")
        .first()
    )

    if existing:
        existing.severity = severity
        existing.description = description
        existing.recommendation = recommendation
        existing.action_url = action_url
        # Bump timestamp so it shows as "just now"
        existing.created_at = timezone.now()
        existing.save(
            update_fields=[
                "severity",
                "description",
                "recommendation",
                "action_url",
                "created_at",
            ]
        )
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
        from tenants.models import DatabaseAssignment
        from tenants.routers import get_current_db_alias

        notif_type = _SEVERITY_TO_NOTIF_TYPE.get(
            insight.severity,
            Notification.NotificationType.INFO,
        )

        # Message includes the recommendation when available
        message = insight.description
        if insight.recommendation:
            message += f"\n\nRecommendation: {insight.recommendation}"

        # Target URL: use the insight's action_url, falling back to the
        # AI dashboard so the user can see full details.
        action_url = insight.action_url or "/erp/ai/"

        recipients = [
            emp.user
            for emp in Employee.objects.filter(
                company=insight.company,
                user__isnull=False,
                employment_status="active",
            ).select_related("user")
            if emp.user and emp.user.is_active
        ]

        # Fallback for imported/demo datasets where employees are not linked
        # to user accounts: notify active approved users assigned to the
        # current tenant database.
        if not recipients:
            current_db_alias = get_current_db_alias()
            assignment_qs = DatabaseAssignment.objects.filter(
                is_active=True,
                user__is_active=True,
                user__is_approved=True,
                database__status="active",
            ).select_related("user", "database")

            # In this codebase, tenant context is tracked via alias like
            # "tenant_<database_uuid>". Use that for precise recipient
            # scoping instead of the SQL connection NAME.
            if current_db_alias and current_db_alias != "default" and current_db_alias.startswith("tenant_"):
                tenant_db_id = current_db_alias.replace("tenant_", "", 1)
                assignment_qs = assignment_qs.filter(database_id=tenant_db_id)
            recipients = [a.user for a in assignment_qs if a.user]

        # De-duplicate recipients by user id
        deduped_recipients = []
        seen_user_ids = set()
        for user in recipients:
            if user.pk in seen_user_ids:
                continue
            seen_user_ids.add(user.pk)
            deduped_recipients.append(user)

        notifications = [
            Notification(
                recipient=user,
                notification_type=notif_type,
                title=f"[AI] {insight.title}",
                message=message,
                action_url=action_url,
            )
            for user in deduped_recipients
        ]

        if notifications:
            Notification.objects.bulk_create(notifications)
            logger.info(
                'AI notification sent to %d users for insight "%s"',
                len(notifications),
                insight.title,
            )
    except Exception as exc:
        # Never let a notification failure break the AI pipeline
        logger.exception("Failed to send AI notifications: %s", exc)
