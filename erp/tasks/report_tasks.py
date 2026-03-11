"""
Celery tasks for the Report Builder.

generate_report  — Async report generation with per-user Redis lock.
cleanup_old_reports — Periodic cleanup of stale generated report files.
"""

import logging

from celery import shared_task
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger('erp.tasks.report')

# Lock TTL: max time a report generation can hold the lock (5 min)
REPORT_LOCK_TTL = 300

# Keep generated reports for N days before auto-cleanup
REPORT_RETENTION_DAYS = 30


def _get_lock_key(user_id):
    return f'report_lock:user:{user_id}'


def user_has_running_report(user_id):
    """Check if a user already has a report generating."""
    return cache.get(_get_lock_key(user_id)) is not None


@shared_task(
    bind=True,
    name='erp.tasks.report.generate_report',
    max_retries=0,
    time_limit=REPORT_LOCK_TTL,
    soft_time_limit=REPORT_LOCK_TTL - 30,
    acks_late=True,
)
def generate_report(self, generated_report_id, db_alias='default'):
    """Generate a report file asynchronously.

    Acquires a per-user Redis lock so only one report can run at a time.
    """
    from erp.models import GeneratedReport
    from erp.services.report_engine import execute_to_list, render_csv, render_excel, render_pdf

    report = GeneratedReport.objects.using(db_alias).select_related(
        'template', 'generated_by',
    ).get(pk=generated_report_id)

    user_id = report.generated_by_id
    lock_key = _get_lock_key(user_id) if user_id else None

    # Acquire lock
    if lock_key and not cache.add(lock_key, str(report.pk), REPORT_LOCK_TTL):
        report.status = GeneratedReport.Status.FAILED
        report.error_message = 'You already have a report generating. Please wait for it to finish.'
        report.save(update_fields=['status', 'error_message'])
        logger.warning('Report %d rejected — user %s already locked', report.pk, user_id)
        return

    report.status = GeneratedReport.Status.PROCESSING
    report.started_at = timezone.now()
    report.celery_task_id = self.request.id or ''
    report.save(update_fields=['status', 'started_at', 'celery_task_id'])

    try:
        config = report.template.configuration
        company = report.template.company

        # Execute query
        result_data = execute_to_list(config, company)
        report.row_count = result_data['row_count']

        # Build date range string for PDF header
        date_range = ''
        if report.date_from and report.date_to:
            date_range = f'{report.date_from.isoformat()} — {report.date_to.isoformat()}'

        # Render output
        fmt = report.output_format
        if fmt == 'csv':
            content = render_csv(result_data)
            filename = f'{report.template.name}.csv'
            content_file = ContentFile(content, name=filename)
        elif fmt == 'excel':
            content = render_excel(result_data, report_name=report.template.name)
            filename = f'{report.template.name}.xlsx'
            content_file = ContentFile(content, name=filename)
        elif fmt == 'pdf':
            content = render_pdf(
                result_data,
                report_name=report.template.name,
                date_range=date_range,
            )
            filename = f'{report.template.name}.pdf'
            content_file = ContentFile(content, name=filename)
        else:
            # HTML — store as html file
            from erp.services.report_engine import render_html_table
            html_content = render_html_table(result_data)
            filename = f'{report.template.name}.html'
            content_file = ContentFile(html_content.encode('utf-8'), name=filename)

        report.file.save(filename, content_file, save=False)
        report.status = GeneratedReport.Status.COMPLETED
        report.is_ready = True
        report.completed_at = timezone.now()
        report.save(update_fields=[
            'file', 'status', 'is_ready', 'completed_at', 'row_count',
        ])

        logger.info(
            'Report %d generated successfully: %d rows, format=%s',
            report.pk, report.row_count, fmt,
        )

    except Exception as exc:
        logger.exception('Report %d generation failed: %s', report.pk, exc)
        report.status = GeneratedReport.Status.FAILED
        report.error_message = str(exc)[:2000]
        report.completed_at = timezone.now()
        report.save(update_fields=['status', 'error_message', 'completed_at'])

    finally:
        # Release lock
        if lock_key:
            cache.delete(lock_key)


@shared_task(name='erp.tasks.report.cleanup_old_reports')
def cleanup_old_reports():
    """Delete generated report files older than REPORT_RETENTION_DAYS."""
    from erp.models import GeneratedReport

    cutoff = timezone.now() - timezone.timedelta(days=REPORT_RETENTION_DAYS)
    old_reports = GeneratedReport.objects.filter(created_at__lt=cutoff)

    deleted_count = 0
    for report in old_reports.iterator():
        if report.file:
            try:
                report.file.delete(save=False)
            except Exception:
                pass
        deleted_count += 1

    old_reports.delete()
    logger.info('Cleaned up %d old generated reports', deleted_count)
