"""
Celery application configuration for the ERP project.

Start the worker with:
    celery -A erpproject worker --loglevel=info

Start the beat scheduler with:
    celery -A erpproject beat --loglevel=info
"""

import logging
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import before_task_publish, task_postrun, task_prerun

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erpproject.settings')

app = Celery('erpproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ── Queue routing ─────────────────────────────────────────────────────────────
# All erp.ai.tasks.* are routed to the dedicated 'ml' queue, which is consumed
# only by the ML Celery worker (the process that has sklearn/numpy/prophet
# installed).  The standard Celery worker listens to 'celery' and 'default'
# queues and never imports ML code, keeping its memory footprint lean.
app.conf.task_routes = {
    'erp.ai.tasks.*': {'queue': 'ml'},
}


# ── Tenant context propagation across process boundaries ────────────────────
#
# Thread-locals are process-local: a db_alias set by TenantMiddleware in the
# Gunicorn worker is invisible to the Celery worker process.
#
# The three signals below bridge that gap transparently:
#   1. before_task_publish  — stamps the current db_alias into the task header
#                             whenever a task is dispatched from a request context.
#   2. task_prerun          — restores the db_alias in the Celery worker thread
#                             before the task body runs.
#   3. task_postrun         — always clears the context after the task finishes
#                             so the thread is clean for the next task.
#
# This is defence-in-depth.  Tasks that already accept an explicit `db_alias`
# kwarg (e.g. generate_report) should still pass it at the call site so the
# intent is self-documenting.  The signal only acts as a safety net for tasks
# that forget.

@before_task_publish.connect
def _inject_tenant_db_alias(headers, **kwargs):
    """Stamp the active tenant db_alias into every outgoing task header."""
    # Lazy import: routers may not be ready at module import time.
    try:
        from tenants.routers import get_current_db_alias
        db_alias = get_current_db_alias()
        if db_alias and db_alias != 'default':
            headers['tenant_db_alias'] = db_alias
        else:
            # A task dispatched without a tenant context will silently fall
            # back to the default (infrastructure) database in the worker.
            # This is almost certainly a bug for tasks that touch tenant data.
            task_name = kwargs.get('sender', '<unknown>')
            logger.warning(
                'Task %s dispatched without a tenant db_alias. '
                'Worker will use the default database. '
                'If this task reads/writes tenant data, set the tenant context '
                'before dispatching.',
                task_name,
            )
    except Exception:
        pass  # Never block task dispatch due to context wiring


@task_prerun.connect
def _restore_tenant_db_alias(task, **kwargs):
    """Restore the tenant db_alias in the worker before the task runs."""
    try:
        from tenants.routers import set_current_db_alias, add_tenant_database
        # task.request.headers contains custom headers added by before_task_publish
        headers = getattr(task.request, 'headers', None) or {}
        db_alias = headers.get('tenant_db_alias')
        if not db_alias:
            return
        from django.conf import settings
        if db_alias not in settings.DATABASES:
            # DB may not be registered yet after a worker restart — re-register it.
            try:
                from tenants.models import TenantDatabase
                db_id = db_alias.replace('tenant_', '')
                tdb = TenantDatabase.objects.get(id=db_id, status='active')
                add_tenant_database(tdb)
            except Exception:
                return  # Can't resolve DB — fall back to default silently
        set_current_db_alias(db_alias)
    except Exception:
        pass


@task_postrun.connect
def _clear_tenant_db_alias(**kwargs):
    """Always wipe the tenant context after a task completes or errors."""
    try:
        from tenants.routers import clear_current_db_alias
        clear_current_db_alias()
    except Exception:
        pass

# ── Beat Schedule (default; can be overridden via django-celery-beat admin) ─
app.conf.beat_schedule = {
    # ── Nightly (2 AM) ──────────────────────────────────────────────────
    'demand-forecast-nightly': {
        'task': 'erp.ai.tasks.retrain_demand_models',
        'schedule': crontab(hour=2, minute=0),
        'options': {'time_limit': 3600, 'soft_time_limit': 3300},
    },
    'score-invoices-daily': {
        'task': 'erp.ai.tasks.score_open_invoices',
        'schedule': crontab(hour=2, minute=30),
        'options': {'time_limit': 1800, 'soft_time_limit': 1500},
    },
    'expense-anomalies-daily': {
        'task': 'erp.ai.tasks.detect_expense_anomalies',
        'schedule': crontab(hour=3, minute=0),
        'options': {'time_limit': 1800, 'soft_time_limit': 1500},
    },
    'kpi-checks-daily': {
        'task': 'erp.ai.tasks.run_kpi_checks',
        'schedule': crontab(hour=3, minute=30),
        'options': {'time_limit': 900, 'soft_time_limit': 800},
    },
    'score-leads-daily': {
        'task': 'erp.ai.tasks.score_active_leads',
        'schedule': crontab(hour=4, minute=0),
        'options': {'time_limit': 1800, 'soft_time_limit': 1500},
    },

    # ── Weekly (Sunday 1 AM) ────────────────────────────────────────────
    'retrain-late-payment-weekly': {
        'task': 'erp.ai.tasks.retrain_late_payment_model',
        'schedule': crontab(hour=1, minute=0, day_of_week='sunday'),
        'options': {'time_limit': 3600, 'soft_time_limit': 3300},
    },
    'cash-flow-forecast-weekly': {
        'task': 'erp.ai.tasks.forecast_cash_flow',
        'schedule': crontab(hour=1, minute=30, day_of_week='sunday'),
        'options': {'time_limit': 1800, 'soft_time_limit': 1500},
    },
    'retrain-lead-scoring-weekly': {
        'task': 'erp.ai.tasks.retrain_lead_scoring_model',
        'schedule': crontab(hour=2, minute=0, day_of_week='sunday'),
        'options': {'time_limit': 3600, 'soft_time_limit': 3300},
    },
    'score-attrition-weekly': {
        'task': 'erp.ai.tasks.score_employee_attrition',
        'schedule': crontab(hour=2, minute=30, day_of_week='sunday'),
        'options': {'time_limit': 1800, 'soft_time_limit': 1500},
    },
    'attendance-anomalies-weekly': {
        'task': 'erp.ai.tasks.detect_attendance_anomalies',
        'schedule': crontab(hour=3, minute=0, day_of_week='sunday'),
        'options': {'time_limit': 1800, 'soft_time_limit': 1500},
    },
    'xai-explanations-weekly': {
        'task': 'erp.ai.tasks.generate_xai_explanations',
        'schedule': crontab(hour=3, minute=30, day_of_week='sunday'),
        'options': {'time_limit': 1800, 'soft_time_limit': 1500},
    },

    # ── Monthly (1st of month, 1 AM) ───────────────────────────────────
    'retrain-attrition-monthly': {
        'task': 'erp.ai.tasks.retrain_attrition_model',
        'schedule': crontab(hour=1, minute=0, day_of_month='1'),
        'options': {'time_limit': 3600, 'soft_time_limit': 3300},
    },
    # ── Platform Admin Automation ───────────────────────────────────────
    'collect-metric-snapshots': {
        'task': 'tenants.collect_metric_snapshots',
        'schedule': crontab(minute='*/30'),          # every 30 min
        'options': {'time_limit': 240, 'soft_time_limit': 200},
    },
    'evaluate-alert-rules': {
        'task': 'tenants.evaluate_alert_rules',
        'schedule': crontab(minute='*/5'),            # every 5 min
        'options': {'time_limit': 180, 'soft_time_limit': 150},
    },
    'refresh-quota-usage': {
        'task': 'tenants.refresh_quota_usage',
        'schedule': crontab(minute=15),               # hourly at :15
        'options': {'time_limit': 180, 'soft_time_limit': 150},
    },
    'dispatch-scheduled-tasks': {
        'task': 'tenants.dispatch_scheduled_tasks',
        'schedule': crontab(minute='*/1'),             # every minute
        'options': {'time_limit': 30, 'soft_time_limit': 25},
    },
    'cleanup-old-metrics': {
        'task': 'tenants.cleanup_old_metrics',
        'schedule': crontab(hour=4, minute=0, day_of_week='sunday'),
        'options': {'time_limit': 600, 'soft_time_limit': 540},
    },
    # ── Report Builder ──────────────────────────────────────────────────
    'cleanup-old-generated-reports': {
        'task': 'erp.tasks.report.cleanup_old_reports',
        'schedule': crontab(hour=4, minute=30),       # daily at 4:30 AM
        'options': {'time_limit': 600, 'soft_time_limit': 540},
    },
}
