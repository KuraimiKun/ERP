"""
Celery tasks for AI / ML periodic jobs.

Scheduled via django-celery-beat.

Each task iterates over every active tenant database, switches context
with TenantDatabaseContext, and then runs the service for each company
found in that tenant's database.  This guarantees full tenant isolation.
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.apps import apps
from django.utils import timezone

logger = logging.getLogger('erp.ai.tasks')


def _for_each_tenant_company(process_fn, task_label='AI task'):
    """Execute *process_fn(company)* for every active company in every tenant DB.

    Handles:
    * Dynamically registering tenant DB connections.
    * Setting TenantDatabaseContext so all ORM queries inside *process_fn*
      hit the correct tenant database.
    * Per-company error isolation (one failure doesn't break others).
    """
    from tenants.routers import TenantDatabaseContext, add_tenant_database

    TenantDatabase = apps.get_model('tenants', 'TenantDatabase')
    Company = apps.get_model('erp', 'Company')

    tenant_dbs = TenantDatabase.objects.filter(status='active')

    for tenant_db in tenant_dbs:
        db_alias = add_tenant_database(tenant_db)

        with TenantDatabaseContext(db_alias):
            try:
                companies = Company.objects.using(db_alias).filter(is_active=True)
            except Exception as exc:
                logger.warning(
                    '%s – cannot query companies in %s: %s',
                    task_label, db_alias, exc,
                )
                continue

            for company in companies:
                if not getattr(company, 'ai_enabled', True):
                    logger.debug(
                        '%s – skipping company %d (AI disabled)',
                        task_label, company.pk,
                    )
                    continue
                try:
                    process_fn(company)
                except Exception as exc:
                    logger.exception(
                        '%s failed for company %d in %s: %s',
                        task_label, company.pk, db_alias, exc,
                    )


# ════════════════════════════════════════════════════════════════════════════
#  Demand Forecasting
# ════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='erp.ai.tasks.retrain_demand_models',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def retrain_demand_models():
    """Nightly: retrain demand forecast models for all tenant companies."""
    from erp.ai.services.demand import DemandForecaster

    def run(company):
        results = DemandForecaster(company).update_all_reorder_rules()
        logger.info('Demand forecast – company %d: %d rules updated',
                    company.pk, len(results))

    _for_each_tenant_company(run, 'Demand forecast')


# ════════════════════════════════════════════════════════════════════════════
#  Finance
# ════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='erp.ai.tasks.retrain_late_payment_model',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def retrain_late_payment_model():
    """Weekly: retrain the late-payment classifier."""
    from erp.ai.services.finance import LatePaymentPredictor

    def run(company):
        result = LatePaymentPredictor(company).train()
        logger.info('Late-payment model – company %d: %s', company.pk, result)

    _for_each_tenant_company(run, 'Late-payment training')


@shared_task(
    name='erp.ai.tasks.score_open_invoices',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def score_open_invoices():
    """Daily: score all open invoices for late-payment risk."""
    from erp.ai.services.finance import LatePaymentPredictor

    def run(company):
        results = LatePaymentPredictor(company).score_all_open_invoices()
        logger.info('Invoice scoring – company %d: %d invoices scored',
                    company.pk, len(results))

    _for_each_tenant_company(run, 'Invoice scoring')


@shared_task(
    name='erp.ai.tasks.detect_expense_anomalies',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def detect_expense_anomalies():
    """Daily: run expense anomaly detection."""
    from erp.ai.services.finance import ExpenseAnomalyDetector

    def run(company):
        results = ExpenseAnomalyDetector(company).detect()
        logger.info('Expense anomalies – company %d: %d anomalies',
                    company.pk, len(results))

    _for_each_tenant_company(run, 'Expense anomaly detection')


@shared_task(
    name='erp.ai.tasks.forecast_cash_flow',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def forecast_cash_flow():
    """Weekly: generate cash-flow projections."""
    from erp.ai.services.finance import CashFlowForecaster

    def run(company):
        result = CashFlowForecaster(company).forecast()
        logger.info('Cash flow forecast – company %d: %s',
                    company.pk, result.get('summary', {}).get('30d', {}))

    _for_each_tenant_company(run, 'Cash flow forecast')


# ════════════════════════════════════════════════════════════════════════════
#  CRM
# ════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='erp.ai.tasks.retrain_lead_scoring_model',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def retrain_lead_scoring_model():
    """Weekly: retrain lead scoring model."""
    from erp.ai.services.crm import LeadScorer

    def run(company):
        result = LeadScorer(company).train()
        logger.info('Lead scoring model – company %d: %s', company.pk, result)

    _for_each_tenant_company(run, 'Lead scoring training')


@shared_task(
    name='erp.ai.tasks.score_active_leads',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def score_active_leads():
    """Daily: score all active leads."""
    from erp.ai.services.crm import LeadScorer

    def run(company):
        results = LeadScorer(company).score_all_active_leads()
        logger.info('Lead scoring – company %d: %d leads scored',
                    company.pk, len(results))

    _for_each_tenant_company(run, 'Lead scoring')


# ════════════════════════════════════════════════════════════════════════════
#  HR
# ════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='erp.ai.tasks.retrain_attrition_model',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def retrain_attrition_model():
    """Monthly: retrain attrition predictor."""
    from erp.ai.services.hr import AttritionPredictor

    def run(company):
        result = AttritionPredictor(company).train()
        logger.info('Attrition model – company %d: %s', company.pk, result)

    _for_each_tenant_company(run, 'Attrition training')


@shared_task(
    name='erp.ai.tasks.score_employee_attrition',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def score_employee_attrition():
    """Weekly: score active employees for attrition risk."""
    from erp.ai.services.hr import AttritionPredictor

    def run(company):
        results = AttritionPredictor(company).score_all_active_employees()
        logger.info('Attrition scoring – company %d: %d employees scored',
                    company.pk, len(results))

    _for_each_tenant_company(run, 'Attrition scoring')


@shared_task(
    name='erp.ai.tasks.detect_attendance_anomalies',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def detect_attendance_anomalies():
    """Weekly: detect attendance anomalies."""
    from erp.ai.services.hr import AttendanceAnomalyDetector

    def run(company):
        results = AttendanceAnomalyDetector(company).detect()
        logger.info('Attendance anomalies – company %d: %d anomalies',
                    company.pk, len(results))

    _for_each_tenant_company(run, 'Attendance anomaly detection')


# ════════════════════════════════════════════════════════════════════════════
#  KPI Anomaly Detection
# ════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='erp.ai.tasks.run_kpi_checks',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def run_kpi_checks():
    """Daily: run KPI anomaly checks."""
    from erp.ai.services.kpi import KPIAnomalyDetector

    def run(company):
        results = KPIAnomalyDetector(company).run_all_checks()
        logger.info('KPI checks – company %d: %d alerts generated',
                    company.pk, len(results))

    _for_each_tenant_company(run, 'KPI checks')


# ════════════════════════════════════════════════════════════════════════════
#  Explainable AI (XAI)
# ════════════════════════════════════════════════════════════════════════════

@shared_task(
    name='erp.ai.tasks.generate_xai_explanations',
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def generate_xai_explanations():
    """Weekly: generate SHAP explanations for recent high-risk predictions."""
    from erp.ai.services.explainability import ExplainabilityService
    from erp.ai.models import PredictionLog

    def run(company):
        svc = ExplainabilityService(company)
        # Get recent high-score predictions from the last 7 days
        cutoff = timezone.now() - timedelta(days=7)
        recent = PredictionLog.objects.filter(
            model__company=company,
            created_at__gte=cutoff,
            score__gte=0.6,
        ).select_related('model').order_by('-score')[:50]

        count = 0
        for pred in recent:
            try:
                svc.explain_prediction(
                    model_type=pred.model.model_type,
                    entity_type=pred.entity_type,
                    entity_id=pred.entity_id,
                    method='shap',
                )
                count += 1
            except Exception as exc:
                logger.debug(
                    'XAI explanation skipped for %s#%s: %s',
                    pred.entity_type, pred.entity_id, exc,
                )
        logger.info('XAI explanations – company %d: %d generated',
                    company.pk, count)

    _for_each_tenant_company(run, 'XAI explanations')
