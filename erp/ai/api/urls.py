"""
AI module API URL configuration.
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from . import views

router = SimpleRouter()
router.register("models", views.MLModelViewSet, basename="ai-models")
router.register("predictions", views.PredictionLogViewSet, basename="ai-predictions")
router.register("insights", views.AIInsightViewSet, basename="ai-insights")
router.register("explanations", views.ExplanationResultViewSet, basename="ai-explanations")

urlpatterns = [
    # ViewSet routes
    path("", include(router.urls)),
    # On-demand triggers
    path("trigger/lead-scoring/", views.trigger_lead_scoring, name="ai-trigger-lead-scoring"),
    path("trigger/invoice-scoring/", views.trigger_invoice_scoring, name="ai-trigger-invoice-scoring"),
    path("trigger/expense-anomaly/", views.trigger_expense_anomaly, name="ai-trigger-expense-anomaly"),
    path("trigger/demand-forecast/", views.trigger_demand_forecast, name="ai-trigger-demand-forecast"),
    path("trigger/attrition/", views.trigger_attrition_scoring, name="ai-trigger-attrition"),
    path("trigger/kpi-checks/", views.trigger_kpi_checks, name="ai-trigger-kpi-checks"),
    # On-demand retraining
    path("trigger/retrain/lead-scoring/", views.trigger_retrain_lead_scoring, name="ai-retrain-lead-scoring"),
    path("trigger/retrain/late-payment/", views.trigger_retrain_late_payment, name="ai-retrain-late-payment"),
    path("trigger/retrain/attrition/", views.trigger_retrain_attrition, name="ai-retrain-attrition"),
    path("trigger/retrain/demand-forecast/", views.trigger_retrain_demand_forecast, name="ai-retrain-demand-forecast"),
    path("trigger/retrain/all/", views.trigger_retrain_all_models, name="ai-retrain-all-models"),
    # Training status / history / cancel
    path("training/status/", views.training_status, name="ai-training-status"),
    path("training/history/", views.training_history, name="ai-training-history"),
    path("training/cancel/", views.cancel_training_run, name="ai-training-cancel"),
    # Cash flow
    path("cashflow/", views.cash_flow_forecast, name="ai-cashflow"),
    # AI Assistant
    path("assistant/", views.ai_assistant_query, name="ai-assistant"),
    # Dashboard summary
    path("dashboard/", views.ai_dashboard_summary, name="ai-dashboard-summary"),
    # XAI – Explainable AI
    path("xai/explain/", views.xai_explain, name="ai-xai-explain"),
    path("xai/global/<str:model_type>/", views.xai_global_importance, name="ai-xai-global"),
]
