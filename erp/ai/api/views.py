"""
AI API Views – REST endpoints for the AI / ML module.
"""

import logging
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import viewsets, mixins
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.ratelimit import HeavyOperationThrottle
from erp.api.permissions import IsCompanyUser, IsAIEnabled

from erp.views._common import get_user_company
from erp.ai.models import (
    MLModel,
    PredictionLog,
    AIInsight,
    ExplanationResult,
    AITrainingRun,
)
from erp.ai.api import (
    MLModelSerializer, PredictionLogSerializer, AIInsightSerializer,
    AssistantQuerySerializer, ExplanationResultSerializer,
    ExplainRequestSerializer, AITrainingRunSerializer,
)

logger = logging.getLogger('erp.ai.api')


def _as_bool(value, default=False):
    """Parse loose bool-like values from JSON payloads."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _wants_evaluation(request) -> bool:
    data = getattr(request, 'data', {}) or {}
    return _as_bool(data.get('evaluate'), default=False)


def _retrain_lead_scoring(company, evaluate=False):
    from erp.ai.services.crm import LeadScorer

    scorer = LeadScorer(company)
    result = scorer.train()
    payload = {
        'status': result.get('status', 'unknown'),
        'auc': result.get('auc'),
        'samples': result.get('samples', 0),
        'reason': result.get('reason', ''),
    }
    if payload['status'] == 'trained' and evaluate:
        scored = scorer.score_all_active_leads()
        payload['evaluation'] = {
            'leads_scored': len(scored),
            'hot': sum(1 for s in scored if s.get('level') == 'hot'),
            'warm': sum(1 for s in scored if s.get('level') == 'warm'),
            'cold': sum(1 for s in scored if s.get('level') == 'cold'),
        }
    return payload


def _retrain_late_payment(company, evaluate=False):
    from erp.ai.services.finance import LatePaymentPredictor

    predictor = LatePaymentPredictor(company)
    result = predictor.train()
    payload = {
        'status': result.get('status', 'unknown'),
        'auc': result.get('auc'),
        'samples': result.get('samples', 0),
        'reason': result.get('reason', ''),
    }
    if payload['status'] == 'trained' and evaluate:
        scored = predictor.score_all_open_invoices()
        payload['evaluation'] = {
            'invoices_scored': len(scored),
            'high_risk': sum(1 for s in scored if s.get('risk_level') == 'high'),
            'medium_risk': sum(1 for s in scored if s.get('risk_level') == 'medium'),
            'low_risk': sum(1 for s in scored if s.get('risk_level') == 'low'),
        }
    return payload


def _retrain_attrition(company, evaluate=False):
    from erp.ai.services.hr import AttritionPredictor

    predictor = AttritionPredictor(company)
    result = predictor.train()
    payload = {
        'status': result.get('status', 'unknown'),
        'auc': result.get('auc'),
        'samples': result.get('samples', 0),
        'reason': result.get('reason', ''),
    }
    if payload['status'] == 'trained' and evaluate:
        scored = predictor.score_all_active_employees()
        payload['evaluation'] = {
            'employees_scored': len(scored),
            'high_risk': sum(1 for s in scored if s.get('risk_level') == 'high'),
            'medium_risk': sum(1 for s in scored if s.get('risk_level') == 'medium'),
            'low_risk': sum(1 for s in scored if s.get('risk_level') == 'low'),
        }
    return payload


def _retrain_demand_forecast(company):
    try:
        from prophet import Prophet  # noqa: F401
    except Exception:
        return {
            'status': 'skipped',
            'reason': 'prophet_not_installed',
            'rules_updated': 0,
        }

    from erp.ai.services.demand import DemandForecaster

    results = DemandForecaster(company).update_all_reorder_rules()
    if not results:
        return {
            'status': 'skipped',
            'reason': 'no_reorder_rules_updated',
            'rules_updated': 0,
        }
    return {
        'status': 'completed',
        'rules_updated': len(results),
    }


def _safe_retrain_step(step_name, fn):
    try:
        return fn()
    except Exception as exc:
        logger.exception('Retrain step failed for %s: %s', step_name, exc)
        return {'status': 'error', 'error': str(exc)}


_STUCK_RUN_TIMEOUT_MINUTES = 30


def _expire_stuck_runs(company):
    """Mark any IN_PROGRESS runs older than _STUCK_RUN_TIMEOUT_MINUTES as FAILED."""
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(minutes=_STUCK_RUN_TIMEOUT_MINUTES)
    stuck = AITrainingRun.objects.filter(
        company=company,
        status=AITrainingRun.Status.IN_PROGRESS,
        started_at__lt=cutoff,
    )
    for run in stuck:
        _finalize_training_run(
            run,
            status=AITrainingRun.Status.FAILED,
            error_message=(
                f'Training timed out after {_STUCK_RUN_TIMEOUT_MINUTES} minutes. '
                'No Celery ML worker processed the task.'
            ),
        )
        logger.warning('Expired stuck training run pk=%s for company=%s', run.pk, company.pk)


def _get_active_training_run(company):
    return AITrainingRun.objects.filter(
        company=company,
        status=AITrainingRun.Status.IN_PROGRESS,
    ).select_related('requested_by').order_by('-started_at').first()


def _start_training_run(company, user, run_type, evaluate):
    return AITrainingRun.objects.create(
        company=company,
        requested_by=user,
        run_type=run_type,
        evaluate=evaluate,
        status=AITrainingRun.Status.IN_PROGRESS,
        started_at=timezone.now(),
    )


def _coerce_run_status(result_status):
    if result_status in {'trained', 'completed'}:
        return AITrainingRun.Status.COMPLETED
    if result_status == 'skipped':
        return AITrainingRun.Status.SKIPPED
    return AITrainingRun.Status.FAILED


def _finalize_training_run(
    run,
    status,
    summary_message='',
    results=None,
    error_message='',
):
    finished_at = timezone.now()
    run.status = status
    run.finished_at = finished_at
    if run.started_at:
        run.duration_seconds = round(
            (finished_at - run.started_at).total_seconds(), 2,
        )
    run.summary_message = summary_message[:500]
    run.results = results or {}
    run.error_message = error_message
    run.save(update_fields=[
        'status', 'finished_at', 'duration_seconds',
        'summary_message', 'results', 'error_message', 'updated_at',
    ])
    return run


def _single_run_message(label, result):
    status = result.get('status', 'unknown')
    if status in {'trained', 'completed'}:
        return f'{label} retraining completed.'
    if status == 'skipped':
        reason = result.get('reason') or 'no_data'
        return f'{label} retraining skipped ({reason}).'
    return f'{label} retraining failed.'


def _parse_limit(query_value, default=20, max_limit=50):
    try:
        return max(1, min(int(query_value), max_limit))
    except (TypeError, ValueError):
        return default


class MLModelViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for ML model registry."""
    serializer_class = MLModelSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsAIEnabled]

    def get_queryset(self):
        company = get_user_company(self.request.user)
        return MLModel.objects.filter(company=company).order_by('-updated_at')


class PredictionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for prediction audit logs."""
    serializer_class = PredictionLogSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsAIEnabled]

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = PredictionLog.objects.filter(
            model__company=company,
        ).select_related('model').order_by('-created_at')
        # Optional filters
        entity_type = self.request.query_params.get('entity_type')
        entity_id = self.request.query_params.get('entity_id')
        model_type = self.request.query_params.get('model_type')
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        if model_type:
            qs = qs.filter(model__model_type=model_type)
        return qs[:200]


class AIInsightViewSet(mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.UpdateModelMixin,
                       viewsets.GenericViewSet):
    """Insight management – list, read, dismiss."""
    serializer_class = AIInsightSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsAIEnabled]

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = AIInsight.objects.filter(company=company).order_by('-created_at')
        # Filters
        category = self.request.query_params.get('category')
        severity = self.request.query_params.get('severity')
        dismissed = self.request.query_params.get('dismissed')
        if category:
            qs = qs.filter(category=category)
        if severity:
            qs = qs.filter(severity=severity)
        if dismissed is not None:
            qs = qs.filter(is_dismissed=dismissed.lower() == 'true')
        return qs

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Mark an insight as dismissed."""
        from django.utils import timezone
        insight = self.get_object()
        insight.is_dismissed = True
        insight.dismissed_by = request.user
        insight.dismissed_at = timezone.now()
        insight.save(update_fields=['is_dismissed', 'dismissed_by',
                                     'dismissed_at'])
        return Response({'status': 'dismissed'})


# ════════════════════════════════════════════════════════════════════════════
#  On-demand trigger endpoints
# ════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@throttle_classes([HeavyOperationThrottle])
def trigger_lead_scoring(request):
    """Trigger lead scoring on demand."""
    from erp.ai.services.crm import LeadScorer
    company = get_user_company(request.user)
    scorer = LeadScorer(company)
    results = scorer.score_all_active_leads()
    return Response({
        'status': 'ok',
        'results': results,
        'message': f'{len(results)} leads scored',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@throttle_classes([HeavyOperationThrottle])
def trigger_invoice_scoring(request):
    """Trigger late-payment scoring on demand."""
    from erp.ai.services.finance import LatePaymentPredictor
    company = get_user_company(request.user)
    predictor = LatePaymentPredictor(company)
    results = predictor.score_all_open_invoices()
    return Response({
        'status': 'ok',
        'results': results,
        'message': f'{len(results)} invoices scored',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@throttle_classes([HeavyOperationThrottle])
def trigger_expense_anomaly(request):
    """Trigger expense anomaly detection on demand."""
    from erp.ai.services.finance import ExpenseAnomalyDetector
    company = get_user_company(request.user)
    detector = ExpenseAnomalyDetector(company)
    results = detector.detect()
    return Response({
        'status': 'ok',
        'results': results,
        'message': f'{len(results)} anomalies detected',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@throttle_classes([HeavyOperationThrottle])
def trigger_demand_forecast(request):
    """Trigger demand forecasting on demand."""
    from erp.ai.services.demand import DemandForecaster
    company = get_user_company(request.user)
    forecaster = DemandForecaster(company)
    results = forecaster.update_all_reorder_rules()
    return Response({
        'status': 'ok',
        'results': results,
        'message': f'{len(results)} reorder rules updated',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@throttle_classes([HeavyOperationThrottle])
def trigger_attrition_scoring(request):
    """Trigger attrition scoring on demand."""
    from erp.ai.services.hr import AttritionPredictor
    company = get_user_company(request.user)
    predictor = AttritionPredictor(company)
    results = predictor.score_all_active_employees()
    return Response({
        'status': 'ok',
        'results': results,
        'message': f'{len(results)} employees scored',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@cache_page(60 * 60)  # 1 hour
@vary_on_cookie
def cash_flow_forecast(request):
    """Get cash-flow forecast."""
    from erp.ai.services.finance import CashFlowForecaster
    company = get_user_company(request.user)
    periods = int(request.query_params.get('periods', 90))
    forecaster = CashFlowForecaster(company)
    result = forecaster.forecast(periods=min(periods, 365))
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@throttle_classes([HeavyOperationThrottle])
def trigger_kpi_checks(request):
    """Run KPI anomaly checks on demand."""
    from erp.ai.services.kpi import KPIAnomalyDetector
    company = get_user_company(request.user)
    detector = KPIAnomalyDetector(company)
    results = detector.run_all_checks()
    return Response({
        'status': 'ok',
        'results': results,
        'message': f'{len(results)} alerts generated',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser])
@throttle_classes([HeavyOperationThrottle])
def trigger_retrain_lead_scoring(request):
    """Retrain lead scoring model on demand (async via Celery)."""
    from tenants.routers import get_current_db_alias
    from erp.ai.tasks import async_retrain_lead_scoring

    company = get_user_company(request.user)
    evaluate = _wants_evaluation(request)
    db_alias = get_current_db_alias() or 'default'

    active_run = _get_active_training_run(company)
    if active_run:
        return Response({
            'status': 'in_progress',
            'message': 'Another training run is already in progress.',
            'active_run': AITrainingRunSerializer(active_run).data,
        }, status=409)

    run = _start_training_run(
        company, request.user,
        AITrainingRun.RunType.LEAD_SCORING,
        evaluate,
    )

    async_retrain_lead_scoring.delay(company.pk, run.pk, db_alias, evaluate)

    return Response({
        'status': 'started',
        'message': 'Lead scoring retraining started.',
        'run': AITrainingRunSerializer(run).data,
    }, status=202)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser])
@throttle_classes([HeavyOperationThrottle])
def trigger_retrain_late_payment(request):
    """Retrain late-payment model on demand (async via Celery)."""
    from tenants.routers import get_current_db_alias
    from erp.ai.tasks import async_retrain_late_payment

    company = get_user_company(request.user)
    evaluate = _wants_evaluation(request)
    db_alias = get_current_db_alias() or 'default'

    active_run = _get_active_training_run(company)
    if active_run:
        return Response({
            'status': 'in_progress',
            'message': 'Another training run is already in progress.',
            'active_run': AITrainingRunSerializer(active_run).data,
        }, status=409)

    run = _start_training_run(
        company, request.user,
        AITrainingRun.RunType.LATE_PAYMENT,
        evaluate,
    )

    async_retrain_late_payment.delay(company.pk, run.pk, db_alias, evaluate)

    return Response({
        'status': 'started',
        'message': 'Late-payment retraining started.',
        'run': AITrainingRunSerializer(run).data,
    }, status=202)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser])
@throttle_classes([HeavyOperationThrottle])
def trigger_retrain_attrition(request):
    """Retrain attrition model on demand (async via Celery)."""
    from tenants.routers import get_current_db_alias
    from erp.ai.tasks import async_retrain_attrition

    company = get_user_company(request.user)
    evaluate = _wants_evaluation(request)
    db_alias = get_current_db_alias() or 'default'

    active_run = _get_active_training_run(company)
    if active_run:
        return Response({
            'status': 'in_progress',
            'message': 'Another training run is already in progress.',
            'active_run': AITrainingRunSerializer(active_run).data,
        }, status=409)

    run = _start_training_run(
        company, request.user,
        AITrainingRun.RunType.ATTRITION,
        evaluate,
    )

    async_retrain_attrition.delay(company.pk, run.pk, db_alias, evaluate)

    return Response({
        'status': 'started',
        'message': 'Attrition retraining started.',
        'run': AITrainingRunSerializer(run).data,
    }, status=202)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser])
@throttle_classes([HeavyOperationThrottle])
def trigger_retrain_demand_forecast(request):
    """Retrain demand forecast model on demand (async via Celery)."""
    from tenants.routers import get_current_db_alias
    from erp.ai.tasks import async_retrain_demand_forecast

    company = get_user_company(request.user)
    db_alias = get_current_db_alias() or 'default'

    active_run = _get_active_training_run(company)
    if active_run:
        return Response({
            'status': 'in_progress',
            'message': 'Another training run is already in progress.',
            'active_run': AITrainingRunSerializer(active_run).data,
        }, status=409)

    run = _start_training_run(
        company, request.user,
        AITrainingRun.RunType.DEMAND_FORECAST,
        evaluate=False,
    )

    async_retrain_demand_forecast.delay(company.pk, run.pk, db_alias)

    return Response({
        'status': 'started',
        'message': 'Demand forecast retraining started.',
        'run': AITrainingRunSerializer(run).data,
    }, status=202)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser])
@throttle_classes([HeavyOperationThrottle])
def trigger_retrain_all_models(request):
    """Retrain all major models from the dashboard (async via Celery)."""
    from tenants.routers import get_current_db_alias
    from erp.ai.tasks import async_retrain_all_models

    company = get_user_company(request.user)
    evaluate = _wants_evaluation(request)
    db_alias = get_current_db_alias() or 'default'

    active_run = _get_active_training_run(company)
    if active_run:
        return Response({
            'status': 'in_progress',
            'message': 'Another training run is already in progress.',
            'active_run': AITrainingRunSerializer(active_run).data,
        }, status=409)

    run = _start_training_run(
        company, request.user,
        AITrainingRun.RunType.ALL_MODELS,
        evaluate,
    )

    async_retrain_all_models.delay(company.pk, run.pk, db_alias, evaluate)

    return Response({
        'status': 'started',
        'message': 'All-models retraining started.',
        'run': AITrainingRunSerializer(run).data,
    }, status=202)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCompanyUser])
def training_status(request):
    """Return the active run (if any) and latest finished run."""
    company = get_user_company(request.user)

    # Auto-expire runs that have been in-progress too long (worker likely down).
    _expire_stuck_runs(company)

    active_run = _get_active_training_run(company)
    latest_run = AITrainingRun.objects.filter(
        company=company,
    ).select_related('requested_by').order_by('-created_at').first()

    return Response({
        'has_active': bool(active_run),
        'active_run': (
            AITrainingRunSerializer(active_run).data if active_run else None
        ),
        'latest_run': (
            AITrainingRunSerializer(latest_run).data if latest_run else None
        ),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser])
def cancel_training_run(request):
    """Cancel (mark as failed) any active training run for this company."""
    company = get_user_company(request.user)
    active_run = _get_active_training_run(company)
    if not active_run:
        return Response({'status': 'ok', 'message': 'No active run to cancel.'}, status=200)

    _finalize_training_run(
        active_run,
        status=AITrainingRun.Status.FAILED,
        error_message='Cancelled by user.',
    )
    return Response({'status': 'cancelled', 'message': 'Training run cancelled.'}, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCompanyUser])
def training_history(request):
    """Return recent retraining history for the current company."""
    company = get_user_company(request.user)
    limit = _parse_limit(request.query_params.get('limit'))

    runs = list(
        AITrainingRun.objects.filter(company=company)
        .select_related('requested_by')
        .order_by('-created_at')[:limit]
    )

    return Response({
        'count': len(runs),
        'results': AITrainingRunSerializer(runs, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@throttle_classes([HeavyOperationThrottle])
def ai_assistant_query(request):
    """Process a natural-language ERP query."""
    serializer = AssistantQuerySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    from erp.ai.services.assistant import ERPAssistant
    company = get_user_company(request.user)
    assistant = ERPAssistant(company, user=request.user)
    result = assistant.query(serializer.validated_data['question'])
    return Response(result)


# ════════════════════════════════════════════════════════════════════════════
#  AI Dashboard Summary
# ════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@cache_page(60 * 10)  # 10 minutes
@vary_on_cookie
def ai_dashboard_summary(request):
    """Return a summary for the AI dashboard widgets."""
    company = get_user_company(request.user)

    # Active insights counts — single aggregate instead of 3 separate queries
    active_insights = AIInsight.objects.filter(
        company=company, is_dismissed=False,
    )
    severity_counts = active_insights.aggregate(
        critical=Count('id', filter=Q(severity=AIInsight.Severity.CRITICAL)),
        warning=Count('id', filter=Q(severity=AIInsight.Severity.WARNING)),
        info=Count('id', filter=Q(severity=AIInsight.Severity.INFO)),
    )
    critical_count = severity_counts['critical']
    warning_count = severity_counts['warning']
    info_count = severity_counts['info']

    # Model stats
    models = MLModel.objects.filter(company=company, is_active=True)
    model_stats = []
    for m in models:
        model_stats.append({
            'name': m.name,
            'type': m.model_type,
            'accuracy': m.accuracy_score,
            'samples': m.training_samples,
            'last_trained': m.last_trained_at,
        })

    # Recent insights
    recent = AIInsightSerializer(
        active_insights[:10], many=True,
    ).data

    return Response({
        'insights': {
            'critical': critical_count,
            'warning': warning_count,
            'info': info_count,
            'total': critical_count + warning_count + info_count,
        },
        'models': model_stats,
        'recent_insights': recent,
    })


# ════════════════════════════════════════════════════════════════════════════
#  Explainable AI (XAI) API
# ════════════════════════════════════════════════════════════════════════════

class ExplanationResultViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for stored explanation results."""
    serializer_class = ExplanationResultSerializer
    permission_classes = [IsAuthenticated, IsCompanyUser, IsAIEnabled]

    def get_queryset(self):
        company = get_user_company(self.request.user)
        qs = ExplanationResult.objects.filter(
            model__company=company,
        ).select_related('model').order_by('-created_at')

        model_type = self.request.query_params.get('model_type')
        entity_type = self.request.query_params.get('entity_type')
        entity_id = self.request.query_params.get('entity_id')
        method = self.request.query_params.get('method')

        if model_type:
            qs = qs.filter(model__model_type=model_type)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        if method:
            qs = qs.filter(method=method)
        return qs[:200]


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
def xai_explain(request):
    """Generate an XAI explanation for a single prediction."""
    serializer = ExplainRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    from erp.ai.services.explainability import ExplainabilityService
    company = get_user_company(request.user)
    svc = ExplainabilityService(company)
    result = svc.explain_prediction(
        model_type=serializer.validated_data['model_type'],
        entity_type=serializer.validated_data['entity_type'],
        entity_id=serializer.validated_data['entity_id'],
        method=serializer.validated_data['method'],
    )
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCompanyUser, IsAIEnabled])
@cache_page(60 * 30)  # 30 minutes
@vary_on_cookie
def xai_global_importance(request, model_type):
    """Return global feature importance for a model type."""
    from erp.ai.services.explainability import ExplainabilityService
    company = get_user_company(request.user)
    svc = ExplainabilityService(company)
    result = svc.global_feature_importance(model_type)
    return Response(result)
