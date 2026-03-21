"""
ERP Views – Report Builder

Custom report designer: list, create/edit builder, generated reports history.
"""

import json

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from erp.models import ReportTemplate, GeneratedReport
from erp.services.report_builder import get_all_data_sources_meta, validate_configuration
from erp.services.report_engine import execute_to_list
from ._common import (
    render, get_object_or_404, redirect, messages,
    get_user_company, staff_member_required, paginate_qs,
)


# ── Report Template List ────────────────────────────────────────────────────

@staff_member_required
def report_builder_list(request):
    """List all report templates the user can access."""
    company = get_user_company(request.user)
    templates = ReportTemplate.objects.filter(
        company=company,
    ).filter(
        Q(created_by=request.user) | Q(is_public=True)
    ).order_by('-updated_at')

    search = request.GET.get('search', '').strip()
    if search:
        templates = templates.filter(name__icontains=search)

    report_type = request.GET.get('type')
    if report_type:
        templates = templates.filter(report_type=report_type)

    page_obj, query_string = paginate_qs(request, templates)

    return render(request, 'erp/reports/report_builder_list.html', {
        'templates': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'report_types': ReportTemplate.ReportType.choices,
    })


# ── Report Builder (Create / Edit) ──────────────────────────────────────────

@staff_member_required
def report_builder_create(request):
    """Report designer — create a new template."""
    data_sources = get_all_data_sources_meta()

    return render(request, 'erp/reports/report_builder.html', {
        'template': None,
        'data_sources_json': json.dumps(data_sources),
        'report_types': ReportTemplate.ReportType.choices,
        'output_formats': ReportTemplate.OutputFormat.choices,
    })


@staff_member_required
def report_builder_edit(request, pk):
    """Report designer — edit an existing template."""
    company = get_user_company(request.user)
    template = get_object_or_404(ReportTemplate, pk=pk, company=company)

    # Only owner or public templates can be edited by others
    if template.created_by != request.user and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to edit this report.')
        return redirect('erp:report_builder_list')

    data_sources = get_all_data_sources_meta()

    return render(request, 'erp/reports/report_builder.html', {
        'template': template,
        'template_json': json.dumps({
            'id': template.pk,
            'name': template.name,
            'report_type': template.report_type,
            'description': template.description,
            'configuration': template.configuration,
            'default_format': template.default_format,
            'is_public': template.is_public,
        }),
        'data_sources_json': json.dumps(data_sources),
        'report_types': ReportTemplate.ReportType.choices,
        'output_formats': ReportTemplate.OutputFormat.choices,
    })


@staff_member_required
@require_POST
def report_builder_save(request):
    """AJAX endpoint — save (create or update) a report template."""
    company = get_user_company(request.user)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    template_id = body.get('id')
    name = (body.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Report name is required.'}, status=400)

    configuration = body.get('configuration', {})
    if configuration and configuration.get('data_source'):
        is_valid, errors = validate_configuration(configuration)
        if not is_valid:
            return JsonResponse({'error': '; '.join(errors)}, status=400)

    if template_id:
        template = get_object_or_404(ReportTemplate, pk=template_id, company=company)
        if template.created_by != request.user and not request.user.is_superuser:
            return JsonResponse({'error': 'Permission denied.'}, status=403)
        if template.is_system:
            return JsonResponse({'error': 'System reports cannot be modified.'}, status=403)
    else:
        template = ReportTemplate(company=company, created_by=request.user)

    template.name = name
    template.report_type = body.get('report_type', 'custom')
    template.description = body.get('description', '')
    template.configuration = configuration
    template.default_format = body.get('default_format', 'pdf')
    template.is_public = bool(body.get('is_public', False))
    template.save()

    return JsonResponse({
        'id': template.pk,
        'name': template.name,
        'message': 'Report template saved successfully.',
    })


@staff_member_required
@require_POST
def report_builder_delete(request, pk):
    """Delete a report template."""
    company = get_user_company(request.user)
    template = get_object_or_404(ReportTemplate, pk=pk, company=company)

    if template.is_system:
        messages.error(request, 'System reports cannot be deleted.')
        return redirect('erp:report_builder_list')

    if template.created_by != request.user and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to delete this report.')
        return redirect('erp:report_builder_list')

    template.delete()
    messages.success(request, f'Report "{template.name}" deleted.')
    return redirect('erp:report_builder_list')


@staff_member_required
@require_POST
def report_builder_preview(request, pk):
    """AJAX — return preview data (first 50 rows) as JSON."""
    company = get_user_company(request.user)
    template = get_object_or_404(ReportTemplate, pk=pk, company=company)
    config = template.configuration

    if not config or not config.get('data_source'):
        return JsonResponse({'error': 'Template has no data source configured.'}, status=400)

    try:
        result = execute_to_list(config, company, limit=50)
        return JsonResponse(result, safe=False)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@staff_member_required
@require_POST
def report_builder_generate(request, pk):
    """AJAX — kick off async report generation."""
    company = get_user_company(request.user)
    template = get_object_or_404(ReportTemplate, pk=pk, company=company)

    config = template.configuration
    if not config or not config.get('data_source'):
        return JsonResponse({'error': 'Template has no data source configured.'}, status=400)

    from erp.tasks.report_tasks import user_has_running_report, generate_report

    if user_has_running_report(request.user.pk):
        return JsonResponse({
            'error': 'You already have a report generating. Please wait for it to finish.',
        }, status=429)

    try:
        body = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        body = {}

    output_format = body.get('output_format', template.default_format)

    generated = GeneratedReport.objects.create(
        template=template,
        generated_by=request.user,
        output_format=output_format,
        date_from=body.get('date_from'),
        date_to=body.get('date_to'),
        parameters=body.get('parameters', {}),
        status=GeneratedReport.Status.PENDING,
    )

    from tenants.routers import get_current_db_alias
    generate_report.delay(generated.pk, db_alias=get_current_db_alias())

    return JsonResponse({
        'id': generated.pk,
        'status': generated.status,
        'message': 'Report generation started.',
    })


# ── Generated Reports ───────────────────────────────────────────────────────

@staff_member_required
def generated_report_list(request):
    """List generated reports for the current user."""
    reports = GeneratedReport.objects.filter(
        generated_by=request.user,
    ).select_related('template').order_by('-created_at')

    status_filter = request.GET.get('status')
    if status_filter:
        reports = reports.filter(status=status_filter)

    page_obj, query_string = paginate_qs(request, reports)

    return render(request, 'erp/reports/generated_reports.html', {
        'reports': page_obj,
        'page_obj': page_obj,
        'query_string': query_string,
        'statuses': GeneratedReport.Status.choices,
    })


@staff_member_required
def generated_report_status(request, pk):
    """AJAX — lightweight status check for polling."""
    report = get_object_or_404(GeneratedReport, pk=pk, generated_by=request.user)
    data = {
        'id': report.pk,
        'status': report.status,
        'is_ready': report.is_ready,
        'row_count': report.row_count,
        'error_message': report.error_message,
        'duration': round(report.duration_seconds, 1) if report.duration_seconds else None,
        'download_url': report.file.url if report.file and report.is_ready else None,
    }
    return JsonResponse(data)
