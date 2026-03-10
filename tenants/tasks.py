"""
Celery tasks for platform admin automation.

These tasks handle:
  - Metric snapshot collection (server stats)
  - Alert rule evaluation & firing
  - Tenant quota usage refresh
  - Scheduled task dispatcher (runs due tasks)
  - Usage snapshot collection (per-database)
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Metric Snapshot Collection ──────────────────────────────────────────────

@shared_task(name='tenants.collect_metric_snapshots')
def collect_metric_snapshots():
    """
    Collect CPU / memory / disk / PG stats from every active server
    and store a MetricSnapshot row.
    """
    from tenants.models import PostgresServer, MetricSnapshot
    from tenants.platform_admin.database_service import DatabaseService

    servers = PostgresServer.objects.filter(is_active=True)
    created = 0

    for server in servers:
        try:
            svc = DatabaseService(server)

            # ── System metrics (best-effort) ──
            cpu = memory_pct = memory_mb = disk_pct = disk_mb = 0.0
            net_rx = net_tx = 0.0
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=1)
                vm = psutil.virtual_memory()
                memory_pct = vm.percent
                memory_mb = vm.used / (1024 * 1024)
                du = psutil.disk_usage('/')
                disk_pct = du.percent
                disk_mb = du.used / (1024 * 1024)
                nio = psutil.net_io_counters()
                net_rx = nio.bytes_recv / (1024 * 1024)
                net_tx = nio.bytes_sent / (1024 * 1024)
            except ImportError:
                pass

            # ── PostgreSQL metrics ──
            pg_conns = pg_active = 0
            pg_size = pg_cache = pg_tps = 0.0
            try:
                info = svc.get_server_info()
                pg_conns = info.get('total_connections', 0)
                pg_active = info.get('active_connections', 0)
                pg_size = info.get('total_size_mb', 0.0)
                pg_cache = info.get('cache_hit_ratio', 0.0)
                pg_tps = info.get('transactions_per_sec', 0.0)
            except Exception:
                pass

            MetricSnapshot.objects.create(
                server=server,
                cpu_percent=cpu,
                memory_percent=memory_pct,
                memory_used_mb=memory_mb,
                disk_percent=disk_pct,
                disk_used_mb=disk_mb,
                net_rx_mb=net_rx,
                net_tx_mb=net_tx,
                total_connections=pg_conns,
                active_connections=pg_active,
                total_db_size_mb=pg_size,
                cache_hit_ratio=pg_cache,
                transactions_per_sec=pg_tps,
            )
            created += 1
        except Exception as e:
            logger.error('metric snapshot failed for %s: %s', server.name, e)

    logger.info('Collected %d metric snapshots', created)
    return f'{created} snapshots created'


# ── Alert Rule Evaluation ───────────────────────────────────────────────────

@shared_task(name='tenants.evaluate_alert_rules')
def evaluate_alert_rules():
    """
    Check every active alert rule and fire an Alert if the condition is met
    (and the cooldown has elapsed).
    """
    from tenants.models import AlertRule, Alert, MetricSnapshot

    rules = AlertRule.objects.filter(is_active=True).select_related('server', 'database')
    now = timezone.now()
    fired = 0

    METRIC_EXTRACTORS = {
        'cpu': lambda m: m.cpu_percent,
        'memory': lambda m: m.memory_percent,
        'disk': lambda m: m.disk_percent,
        'connections': lambda m: m.total_connections,
        'db_size': lambda m: m.total_db_size_mb,
        'long_queries': lambda m: 0,
        'replication_lag': lambda m: 0,
    }

    OPS = {
        'gt': lambda v, t: v > t,
        'gte': lambda v, t: v >= t,
        'lt': lambda v, t: v < t,
        'lte': lambda v, t: v <= t,
        'eq': lambda v, t: v == t,
    }

    for rule in rules:
        try:
            # Cooldown check
            last_alert = Alert.objects.filter(
                rule=rule
            ).order_by('-created_at').first()
            if last_alert:
                cooldown = now - timedelta(minutes=rule.cooldown_minutes)
                if last_alert.created_at > cooldown:
                    continue

            # Get latest metric for the server
            server = rule.server
            if not server:
                continue

            metric = MetricSnapshot.objects.filter(
                server=server
            ).order_by('-recorded_at').first()
            if not metric:
                continue

            extractor = METRIC_EXTRACTORS.get(rule.metric)
            op_fn = OPS.get(rule.operator)
            if not extractor or not op_fn:
                continue

            value = extractor(metric)
            if op_fn(value, float(rule.threshold)):
                Alert.objects.create(
                    rule=rule,
                    severity=rule.severity,
                    message=f'{rule.get_metric_display()} is {value} '
                            f'({rule.get_operator_display()} {rule.threshold})',
                    metric_value=value,
                    server=rule.server,
                    database=rule.database,
                )
                rule.trigger_count += 1
                rule.save(update_fields=['trigger_count'])
                fired += 1
        except Exception as e:
            logger.error('Alert rule eval failed for %s: %s', rule.pk, e)

    logger.info('Evaluated alert rules, fired %d alerts', fired)
    return f'{fired} alerts fired'


# ── Quota Usage Refresh ─────────────────────────────────────────────────────

@shared_task(name='tenants.refresh_quota_usage')
def refresh_quota_usage():
    """
    Refresh current_* fields on every TenantQuota from live DB stats,
    and record a UsageSnapshot.
    """
    from tenants.models import TenantQuota, UsageSnapshot
    from tenants.platform_admin.database_service import DatabaseService

    quotas = TenantQuota.objects.select_related(
        'database', 'database__server'
    ).all()
    refreshed = 0

    for quota in quotas:
        try:
            db = quota.database
            if not db.server:
                continue

            svc = DatabaseService(db.server)
            info = svc.get_database_info(db.name)

            quota.current_db_size_mb = info.get('size_mb', 0)
            quota.current_connections = info.get('connections', 0)
            quota.current_tables = info.get('table_count', 0)
            quota.current_storage_mb = info.get('size_mb', 0)
            quota.save(update_fields=[
                'current_db_size_mb', 'current_connections',
                'current_tables', 'current_storage_mb',
            ])

            UsageSnapshot.objects.create(
                database=db,
                db_size_mb=info.get('size_mb', 0),
                connections=info.get('connections', 0),
                table_count=info.get('table_count', 0),
                dead_tuples=info.get('dead_tuples', 0),
                cache_hit_ratio=info.get('cache_hit_ratio', 0),
            )
            refreshed += 1
        except Exception as e:
            logger.error('Quota refresh failed for %s: %s', quota.database.name, e)

    logger.info('Refreshed %d quotas', refreshed)
    return f'{refreshed} quotas refreshed'


# ── Scheduled Task Dispatcher ───────────────────────────────────────────────

@shared_task(name='tenants.dispatch_scheduled_tasks')
def dispatch_scheduled_tasks():
    """
    Check every active ScheduledTask and run it if it's due.
    """
    from tenants.models import ScheduledTask, TaskExecution

    now = timezone.now()
    tasks = ScheduledTask.objects.filter(is_active=True)
    ran = 0

    INTERVAL_DELTAS = {
        'every_30m': timedelta(minutes=30),
        'hourly': timedelta(hours=1),
        'every_6h': timedelta(hours=6),
        'every_12h': timedelta(hours=12),
        'daily': timedelta(days=1),
        'weekly': timedelta(weeks=1),
        'monthly': timedelta(days=30),
    }

    for task in tasks:
        try:
            delta = INTERVAL_DELTAS.get(task.interval, timedelta(days=1))

            # Check if task is due
            if task.last_run and (now - task.last_run) < delta:
                continue

            # For daily+ tasks, check the hour/minute window
            if task.interval in ('daily', 'weekly', 'monthly'):
                if now.hour != task.run_at_hour or abs(now.minute - task.run_at_minute) > 5:
                    continue
                if task.interval == 'weekly' and now.weekday() != task.run_at_day:
                    continue

            # Execute the task
            started = timezone.now()
            execution = TaskExecution.objects.create(
                task=task, status='running', started_at=started,
            )
            try:
                _execute_task(task)
                finished = timezone.now()
                execution.status = 'success'
                execution.finished_at = finished
                execution.duration_seconds = (finished - started).total_seconds()
                execution.message = 'Completed successfully'
                execution.save()

                task.last_run = finished
                task.last_status = 'success'
                task.last_message = 'Completed via scheduler'
                task.run_count += 1
                task.save(update_fields=[
                    'last_run', 'last_status', 'last_message', 'run_count',
                ])
                ran += 1
            except Exception as e:
                finished = timezone.now()
                execution.status = 'failed'
                execution.finished_at = finished
                execution.duration_seconds = (finished - started).total_seconds()
                execution.message = str(e)[:500]
                execution.save()

                task.last_run = finished
                task.last_status = 'failed'
                task.last_message = str(e)[:200]
                task.save(update_fields=[
                    'last_run', 'last_status', 'last_message',
                ])
        except Exception as e:
            logger.error('Dispatcher failed for task %s: %s', task.pk, e)

    logger.info('Dispatcher ran %d tasks', ran)
    return f'{ran} tasks executed'


def _execute_task(task):
    """Actually run the maintenance / backup task."""
    from tenants.platform_admin.database_service import DatabaseService

    svc = None
    if task.server:
        svc = DatabaseService(task.server)

    if task.task_type == 'backup' and task.database and svc:
        svc.backup_database(task.database.name)
    elif task.task_type in ('vacuum', 'vacuum_full', 'analyze',
                            'vacuum_analyze', 'reindex') and task.database and svc:
        svc.run_maintenance(task.database.name, task.task_type)
    elif task.task_type == 'health_check' and svc:
        svc.get_server_info()
    elif task.task_type == 'metric_snapshot':
        collect_metric_snapshots.apply()
    else:
        raise ValueError(f'Cannot execute task type: {task.task_type}')


# ── Cleanup Old Data ────────────────────────────────────────────────────────

@shared_task(name='tenants.cleanup_old_metrics')
def cleanup_old_metrics(days=90):
    """Delete MetricSnapshot, UsageSnapshot, and resolved alerts older than N days."""
    from tenants.models import MetricSnapshot, UsageSnapshot, Alert

    cutoff = timezone.now() - timedelta(days=days)

    m_del, _ = MetricSnapshot.objects.filter(recorded_at__lt=cutoff).delete()
    u_del, _ = UsageSnapshot.objects.filter(recorded_at__lt=cutoff).delete()
    a_del, _ = Alert.objects.filter(
        status='resolved', created_at__lt=cutoff
    ).delete()

    msg = f'Cleaned up: {m_del} metrics, {u_del} usage, {a_del} alerts'
    logger.info(msg)
    return msg
