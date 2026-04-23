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
#  On-demand async retrain tasks (triggered from the dashboard)
# ════════════════════════════════════════════════════════════════════════════

def _ensure_tenant_db_registered(db_alias):
    """Register a tenant DB connection in settings.DATABASES if not already present.

    On-demand retrain tasks receive an explicit db_alias (e.g.
    'tenant_7c1b1ae2-...') that was registered dynamically by the web process
    but is not persisted across process boundaries.  The Celery worker must
    re-register it before executing any ORM query against that alias.
    """
    from django.conf import settings
    if db_alias in settings.DATABASES:
        return
    if not db_alias.startswith('tenant_'):
        return
    tenant_id = db_alias[len('tenant_'):]
    from tenants.models import TenantDatabase
    from tenants.routers import add_tenant_database
    tenant_db = TenantDatabase.objects.using('default').get(id=tenant_id)
    add_tenant_database(tenant_db)


def _finalize_run(run_id, status, summary_message, results, error_message=''):
    """Save the final state of an AITrainingRun by its PK."""
    from django.utils import timezone as tz
    from erp.ai.models import AITrainingRun
    try:
        run = AITrainingRun.objects.get(pk=run_id)
        run.status = status
        run.summary_message = summary_message
        run.results = results
        run.error_message = error_message
        run.finished_at = tz.now()
        if run.started_at:
            run.duration_seconds = (run.finished_at - run.started_at).total_seconds()
        run.save(update_fields=[
            'status', 'summary_message', 'results', 'error_message',
            'finished_at', 'duration_seconds',
        ])
    except AITrainingRun.DoesNotExist:
        logger.warning('_finalize_run: AITrainingRun pk=%s not found', run_id)


def _update_run_progress(run_id, step, total, label=''):
    """Update live progress fields on an AITrainingRun."""
    from erp.ai.models import AITrainingRun
    try:
        AITrainingRun.objects.filter(pk=run_id).update(
            progress_step=step,
            progress_total=total,
            progress_label=label,
        )
    except Exception as exc:
        logger.debug('_update_run_progress: could not update run %s: %s', run_id, exc)


def _coerce_status(result_status):
    from erp.ai.models import AITrainingRun
    if result_status in {'trained', 'completed'}:
        return AITrainingRun.Status.COMPLETED
    if result_status == 'skipped':
        return AITrainingRun.Status.SKIPPED
    return AITrainingRun.Status.FAILED


@shared_task(
    name='erp.ai.tasks.async_retrain_lead_scoring',
    max_retries=0,
)
def async_retrain_lead_scoring(company_id, run_id, db_alias, evaluate=False):
    """On-demand: retrain lead scoring model for one company."""
    from tenants.routers import TenantDatabaseContext
    from erp.ai.models import AITrainingRun
    from erp.ai.services.crm import LeadScorer
    from django.apps import apps
    Company = apps.get_model('erp', 'Company')

    _ensure_tenant_db_registered(db_alias)
    with TenantDatabaseContext(db_alias):
        company = Company.objects.using(db_alias).get(pk=company_id)
        try:
            _update_run_progress(run_id, 0, 1, 'Training lead scoring model…')
            result = LeadScorer(company).train()
            status = _coerce_status(result.get('status'))
            _update_run_progress(run_id, 1, 1, 'Finalising…')
            message = (
                f"Lead scoring retraining completed (AUC={result.get('auc', 'N/A')}, "
                f"samples={result.get('samples', 'N/A')})."
                if status == AITrainingRun.Status.COMPLETED
                else f"Lead scoring retraining {result.get('status', 'skipped')} "
                     f"({result.get('reason', '')})."
            )
            _finalize_run(run_id, status, message, {'lead_scoring': result})
        except Exception as exc:
            logger.exception('async_retrain_lead_scoring failed for company %d', company_id)
            _finalize_run(run_id, AITrainingRun.Status.FAILED,
                          'Lead scoring retraining failed.', {}, str(exc))


@shared_task(
    name='erp.ai.tasks.async_retrain_late_payment',
    max_retries=0,
)
def async_retrain_late_payment(company_id, run_id, db_alias, evaluate=False):
    """On-demand: retrain late-payment model for one company."""
    from tenants.routers import TenantDatabaseContext
    from erp.ai.models import AITrainingRun
    from erp.ai.services.finance import LatePaymentPredictor
    from django.apps import apps
    Company = apps.get_model('erp', 'Company')

    _ensure_tenant_db_registered(db_alias)
    with TenantDatabaseContext(db_alias):
        company = Company.objects.using(db_alias).get(pk=company_id)
        try:
            _update_run_progress(run_id, 0, 1, 'Training late payment model…')
            result = LatePaymentPredictor(company).train()
            status = _coerce_status(result.get('status'))
            _update_run_progress(run_id, 1, 1, 'Finalising…')
            message = (
                f"Late payment retraining completed (AUC={result.get('auc', 'N/A')}, "
                f"samples={result.get('samples', 'N/A')})."
                if status == AITrainingRun.Status.COMPLETED
                else f"Late payment retraining {result.get('status', 'skipped')} "
                     f"({result.get('reason', '')})."
            )
            _finalize_run(run_id, status, message, {'late_payment': result})
        except Exception as exc:
            logger.exception('async_retrain_late_payment failed for company %d', company_id)
            _finalize_run(run_id, AITrainingRun.Status.FAILED,
                          'Late payment retraining failed.', {}, str(exc))


@shared_task(
    name='erp.ai.tasks.async_retrain_attrition',
    max_retries=0,
)
def async_retrain_attrition(company_id, run_id, db_alias, evaluate=False):
    """On-demand: retrain attrition model for one company."""
    from tenants.routers import TenantDatabaseContext
    from erp.ai.models import AITrainingRun
    from erp.ai.services.hr import AttritionPredictor
    from django.apps import apps
    Company = apps.get_model('erp', 'Company')

    _ensure_tenant_db_registered(db_alias)
    with TenantDatabaseContext(db_alias):
        company = Company.objects.using(db_alias).get(pk=company_id)
        try:
            _update_run_progress(run_id, 0, 1, 'Training attrition model…')
            result = AttritionPredictor(company).train()
            status = _coerce_status(result.get('status'))
            _update_run_progress(run_id, 1, 1, 'Finalising…')
            message = (
                f"Attrition retraining completed (AUC={result.get('auc', 'N/A')}, "
                f"samples={result.get('samples', 'N/A')})."
                if status == AITrainingRun.Status.COMPLETED
                else f"Attrition retraining {result.get('status', 'skipped')} "
                     f"({result.get('reason', '')})."
            )
            _finalize_run(run_id, status, message, {'attrition': result})
        except Exception as exc:
            logger.exception('async_retrain_attrition failed for company %d', company_id)
            _finalize_run(run_id, AITrainingRun.Status.FAILED,
                          'Attrition retraining failed.', {}, str(exc))


@shared_task(
    name='erp.ai.tasks.async_retrain_demand_forecast',
    max_retries=0,
)
def async_retrain_demand_forecast(company_id, run_id, db_alias):
    """On-demand: retrain demand forecast model for one company."""
    from tenants.routers import TenantDatabaseContext
    from erp.ai.models import AITrainingRun
    from django.apps import apps
    Company = apps.get_model('erp', 'Company')

    _ensure_tenant_db_registered(db_alias)
    with TenantDatabaseContext(db_alias):
        company = Company.objects.using(db_alias).get(pk=company_id)
        try:
            _update_run_progress(run_id, 0, 1, 'Updating demand forecast reorder rules…')
            try:
                from prophet import Prophet  # noqa: F401
            except Exception:
                result = {'status': 'skipped', 'reason': 'prophet_not_installed', 'rules_updated': 0}
            else:
                from erp.ai.services.demand import DemandForecaster
                results = DemandForecaster(company).update_all_reorder_rules()
                if not results:
                    result = {'status': 'skipped', 'reason': 'no_reorder_rules_updated', 'rules_updated': 0}
                else:
                    result = {'status': 'completed', 'rules_updated': len(results)}

            _update_run_progress(run_id, 1, 1, 'Finalising…')
            status = _coerce_status(result.get('status'))
            message = (
                f"Demand forecast retraining completed ({result.get('rules_updated', 0)} rules updated)."
                if status == AITrainingRun.Status.COMPLETED
                else f"Demand forecast retraining skipped ({result.get('reason', '')})."
            )
            _finalize_run(run_id, status, message, {'demand_forecast': result})
        except Exception as exc:
            logger.exception('async_retrain_demand_forecast failed for company %d', company_id)
            _finalize_run(run_id, AITrainingRun.Status.FAILED,
                          'Demand forecast retraining failed.', {}, str(exc))


@shared_task(
    name='erp.ai.tasks.async_retrain_all_models',
    max_retries=0,
)
def async_retrain_all_models(company_id, run_id, db_alias, evaluate=False):
    """On-demand: retrain all major models for one company."""
    from tenants.routers import TenantDatabaseContext
    from erp.ai.models import AITrainingRun
    from erp.ai.services.crm import LeadScorer
    from erp.ai.services.finance import LatePaymentPredictor
    from erp.ai.services.hr import AttritionPredictor
    from erp.ai.services.demand import DemandForecaster
    from django.apps import apps
    Company = apps.get_model('erp', 'Company')

    _ensure_tenant_db_registered(db_alias)
    with TenantDatabaseContext(db_alias):
        company = Company.objects.using(db_alias).get(pk=company_id)
        results = {}

        def _step(key, fn, step_num, step_label):
            _update_run_progress(run_id, step_num - 1, 4, step_label)
            try:
                results[key] = fn()
            except Exception as exc:
                logger.exception('async_retrain_all_models step %s failed for company %d', key, company_id)
                results[key] = {'status': 'error', 'error': str(exc)}

        _step('lead_scoring', lambda: LeadScorer(company).train(),
              1, 'Step 1/4 — Training lead scoring model…')
        _step('late_payment', lambda: LatePaymentPredictor(company).train(),
              2, 'Step 2/4 — Training late payment model…')
        _step('attrition', lambda: AttritionPredictor(company).train(),
              3, 'Step 3/4 — Training attrition model…')
        _update_run_progress(run_id, 3, 4, 'Step 4/4 — Updating demand forecast rules…')

        def _demand_step():
            try:
                from prophet import Prophet  # noqa: F401
            except Exception:
                return {'status': 'skipped', 'reason': 'prophet_not_installed', 'rules_updated': 0}
            results_d = DemandForecaster(company).update_all_reorder_rules()
            if not results_d:
                return {'status': 'skipped', 'reason': 'no_reorder_rules_updated', 'rules_updated': 0}
            return {'status': 'completed', 'rules_updated': len(results_d)}

        _step('demand_forecast', _demand_step, 4, 'Step 4/4 — Updating demand forecast rules…')

        statuses = [v.get('status', 'unknown') for v in results.values()]
        error_count = sum(1 for s in statuses if s == 'error')
        skipped_count = sum(1 for s in statuses if s == 'skipped')
        trained_count = sum(1 for s in statuses if s in {'trained', 'completed'})

        if error_count == len(statuses):
            final_status = AITrainingRun.Status.FAILED
        elif error_count or skipped_count:
            final_status = AITrainingRun.Status.COMPLETED_WITH_WARNINGS
        else:
            final_status = AITrainingRun.Status.COMPLETED

        message = (
            f'Retraining finished: {trained_count} trained, '
            f'{skipped_count} skipped, {error_count} errors.'
        )
        error_msgs = ' | '.join(
            f"{k}: {v.get('error', '')}"
            for k, v in results.items() if v.get('status') == 'error'
        )
        _finalize_run(run_id, final_status, message, results, error_msgs)


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
