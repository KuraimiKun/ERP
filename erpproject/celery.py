"""
Celery application configuration for the ERP project.

Start the worker with:
    celery -A erpproject worker --loglevel=info

Start the beat scheduler with:
    celery -A erpproject beat --loglevel=info
"""

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erpproject.settings')

app = Celery('erpproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ── Beat Schedule (default; can be overridden via django-celery-beat admin) ─
app.conf.beat_schedule = {
    # ── Nightly (2 AM) ──────────────────────────────────────────────────
    'demand-forecast-nightly': {
        'task': 'erp.ai.tasks.retrain_demand_models',
        'schedule': crontab(hour=2, minute=0),
    },
    'score-invoices-daily': {
        'task': 'erp.ai.tasks.score_open_invoices',
        'schedule': crontab(hour=2, minute=30),
    },
    'expense-anomalies-daily': {
        'task': 'erp.ai.tasks.detect_expense_anomalies',
        'schedule': crontab(hour=3, minute=0),
    },
    'kpi-checks-daily': {
        'task': 'erp.ai.tasks.run_kpi_checks',
        'schedule': crontab(hour=3, minute=30),
    },
    'score-leads-daily': {
        'task': 'erp.ai.tasks.score_active_leads',
        'schedule': crontab(hour=4, minute=0),
    },

    # ── Weekly (Sunday 1 AM) ────────────────────────────────────────────
    'retrain-late-payment-weekly': {
        'task': 'erp.ai.tasks.retrain_late_payment_model',
        'schedule': crontab(hour=1, minute=0, day_of_week='sunday'),
    },
    'cash-flow-forecast-weekly': {
        'task': 'erp.ai.tasks.forecast_cash_flow',
        'schedule': crontab(hour=1, minute=30, day_of_week='sunday'),
    },
    'retrain-lead-scoring-weekly': {
        'task': 'erp.ai.tasks.retrain_lead_scoring_model',
        'schedule': crontab(hour=2, minute=0, day_of_week='sunday'),
    },
    'score-attrition-weekly': {
        'task': 'erp.ai.tasks.score_employee_attrition',
        'schedule': crontab(hour=2, minute=30, day_of_week='sunday'),
    },
    'attendance-anomalies-weekly': {
        'task': 'erp.ai.tasks.detect_attendance_anomalies',
        'schedule': crontab(hour=3, minute=0, day_of_week='sunday'),
    },

    # ── Monthly (1st of month, 1 AM) ───────────────────────────────────
    'retrain-attrition-monthly': {
        'task': 'erp.ai.tasks.retrain_attrition_model',
        'schedule': crontab(hour=1, minute=0, day_of_month='1'),
    },
}
