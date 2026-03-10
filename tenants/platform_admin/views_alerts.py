"""
Platform Admin - Alerts & Notifications Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Count, Q

from tenants.models import AlertRule, Alert
from .forms import AlertRuleForm
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_alert_rules(request):
    """List all alert rules."""
    qs = AlertRule.objects.select_related('server', 'database', 'created_by').annotate(
        active_alerts_count=Count('alerts', filter=Q(alerts__status='active')),
        total_alerts_count=Count('alerts'),
    )

    severity = request.GET.get('severity')
    status = request.GET.get('status')
    if severity:
        qs = qs.filter(severity=severity)
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    page_obj = paginate(request, qs, 20)

    context = pa_context(request, {
        'rules': page_obj,
        'current_severity': severity,
        'current_status': status,
    })
    return render(request, 'platform_admin/alerts/rules.html', context)


@platform_admin_required
def pa_alert_rule_create(request):
    """Create a new alert rule."""
    if request.method == 'POST':
        form = AlertRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.created_by = request.user
            rule.save()
            messages.success(request, _('Alert rule created successfully.'))
            return redirect('tenants:pa_alert_rules')
    else:
        form = AlertRuleForm()

    context = pa_context(request, {'form': form})
    return render(request, 'platform_admin/alerts/rule_form.html', context)


@platform_admin_required
def pa_alert_rule_edit(request, pk):
    """Edit an existing alert rule."""
    rule = get_object_or_404(AlertRule, pk=pk)
    if request.method == 'POST':
        form = AlertRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, _('Alert rule updated.'))
            return redirect('tenants:pa_alert_rules')
    else:
        form = AlertRuleForm(instance=rule)

    context = pa_context(request, {'form': form, 'rule': rule, 'editing': True})
    return render(request, 'platform_admin/alerts/rule_form.html', context)


@platform_admin_required
@require_POST
def pa_alert_rule_toggle(request, pk):
    """Toggle an alert rule active/inactive."""
    rule = get_object_or_404(AlertRule, pk=pk)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active'])
    status_text = _('activated') if rule.is_active else _('deactivated')
    messages.success(request, _(f'Alert rule "{rule.name}" {status_text}.'))
    return redirect('tenants:pa_alert_rules')


@platform_admin_required
@require_POST
def pa_alert_rule_delete(request, pk):
    """Delete an alert rule and its alerts."""
    rule = get_object_or_404(AlertRule, pk=pk)
    name = rule.name
    rule.delete()
    messages.success(request, _(f'Alert rule "{name}" deleted.'))
    return redirect('tenants:pa_alert_rules')


@platform_admin_required
def pa_alert_list(request):
    """List all fired alerts with filters."""
    qs = Alert.objects.select_related('rule', 'server', 'database', 'acknowledged_by')

    status = request.GET.get('status')
    severity = request.GET.get('severity')
    if status:
        qs = qs.filter(status=status)
    if severity:
        qs = qs.filter(severity=severity)

    # Stats
    active_count = Alert.objects.filter(status='active').count()
    critical_count = Alert.objects.filter(status='active', severity='critical').count()
    warning_count = Alert.objects.filter(status='active', severity='warning').count()

    page_obj = paginate(request, qs, 30)

    context = pa_context(request, {
        'alerts': page_obj,
        'current_status': status,
        'current_severity': severity,
        'active_count': active_count,
        'critical_count': critical_count,
        'warning_count': warning_count,
    })
    return render(request, 'platform_admin/alerts/list.html', context)


@platform_admin_required
@require_POST
def pa_alert_acknowledge(request, pk):
    """Acknowledge an alert."""
    alert = get_object_or_404(Alert, pk=pk)
    alert.status = 'acknowledged'
    alert.acknowledged_by = request.user
    alert.acknowledged_at = timezone.now()
    alert.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])
    messages.success(request, _('Alert acknowledged.'))
    return redirect('tenants:pa_alert_list')


@platform_admin_required
@require_POST
def pa_alert_resolve(request, pk):
    """Resolve an alert."""
    alert = get_object_or_404(Alert, pk=pk)
    alert.status = 'resolved'
    alert.resolved_at = timezone.now()
    if not alert.acknowledged_by:
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
    alert.save(update_fields=['status', 'resolved_at', 'acknowledged_by', 'acknowledged_at'])
    messages.success(request, _('Alert resolved.'))
    return redirect('tenants:pa_alert_list')


@platform_admin_required
@require_POST
def pa_alert_bulk_action(request):
    """Bulk acknowledge or resolve alerts."""
    action = request.POST.get('action')
    alert_ids = request.POST.getlist('alert_ids')

    if not alert_ids or action not in ('acknowledge', 'resolve'):
        messages.warning(request, _('Invalid action or no alerts selected.'))
        return redirect('tenants:pa_alert_list')

    alerts = Alert.objects.filter(pk__in=alert_ids)
    now = timezone.now()

    if action == 'acknowledge':
        alerts.filter(status='active').update(
            status='acknowledged',
            acknowledged_by=request.user,
            acknowledged_at=now,
        )
        messages.success(request, _(f'{len(alert_ids)} alerts acknowledged.'))
    elif action == 'resolve':
        alerts.exclude(status='resolved').update(
            status='resolved',
            resolved_at=now,
        )
        messages.success(request, _(f'{len(alert_ids)} alerts resolved.'))

    return redirect('tenants:pa_alert_list')


@platform_admin_required
def pa_alert_api(request):
    """JSON endpoint for live alert badge count."""
    active = Alert.objects.filter(status='active').count()
    critical = Alert.objects.filter(status='active', severity='critical').count()
    return JsonResponse({'active': active, 'critical': critical})
