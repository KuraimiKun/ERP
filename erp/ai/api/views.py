"""
AI API Views – REST endpoints for the AI / ML module.
"""

import logging
from django.db.models import Count, Q
from rest_framework import viewsets, mixins
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from erp.ratelimit import HeavyOperationThrottle
from erp.api.permissions import IsCompanyUser, IsAIEnabled

from erp.views._common import get_user_company
from erp.ai.models import MLModel, PredictionLog, AIInsight, ExplanationResult
from erp.ai.api import (
    MLModelSerializer, PredictionLogSerializer, AIInsightSerializer,
    AssistantQuerySerializer, ExplanationResultSerializer, ExplainRequestSerializer,
)

logger = logging.getLogger('erp.ai.api')


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
