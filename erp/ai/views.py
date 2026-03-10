"""
AI Dashboard Views – server-rendered views for the AI insights dashboard.
"""

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _

from erp.decorators import tenant_required
from erp.views._common import get_user_company, paginate_qs
from erp.ai.models import MLModel, PredictionLog, AIInsight


@login_required
@tenant_required
def ai_dashboard(request):
    """Main AI / ML insights dashboard."""
    company = get_user_company(request.user)

    # Active insights
    insights_qs = AIInsight.objects.filter(
        company=company, is_dismissed=False,
    ).order_by('-created_at')

    critical = insights_qs.filter(severity=AIInsight.Severity.CRITICAL)
    warnings = insights_qs.filter(severity=AIInsight.Severity.WARNING)
    infos = insights_qs.filter(severity=AIInsight.Severity.INFO)

    # Model registry
    models = MLModel.objects.filter(
        company=company, is_active=True,
    ).order_by('-last_trained_at')

    # Recent predictions
    predictions = PredictionLog.objects.filter(
        model__company=company,
    ).select_related('model').order_by('-created_at')[:20]

    context = {
        'title': 'AI & ML Insights',
        'critical_insights': critical[:10],
        'warning_insights': warnings[:10],
        'info_insights': infos[:10],
        'total_critical': critical.count(),
        'total_warnings': warnings.count(),
        'total_infos': infos.count(),
        'ml_models': models,
        'recent_predictions': predictions,
    }
    return render(request, 'erp/ai/dashboard.html', context)


@login_required
@tenant_required
def ai_insights_list(request):
    """Full paginated list of AI insights."""
    company = get_user_company(request.user)
    qs = AIInsight.objects.filter(company=company).order_by('-created_at')

    category = request.GET.get('category')
    severity = request.GET.get('severity')
    dismissed = request.GET.get('dismissed')

    if category:
        qs = qs.filter(category=category)
    if severity:
        qs = qs.filter(severity=severity)
    if dismissed is not None:
        qs = qs.filter(is_dismissed=dismissed.lower() == 'true')

    page_obj = paginate_qs(request, qs, per_page=25)
    context = {
        'title': 'AI Insights',
        'page_obj': page_obj,
        'categories': AIInsight.Category.choices,
        'severities': AIInsight.Severity.choices,
        'selected_category': category,
        'selected_severity': severity,
    }
    return render(request, 'erp/ai/insights_list.html', context)


# ── AI Settings ─────────────────────────────────────────────────────────────

class AISettingsForm:
    """Minimal form class for AI settings (subset of Company fields)."""
    pass


@login_required
@tenant_required
def ai_settings(request):
    """Allow each tenant to configure their own OpenAI key and AI toggle."""

    company = get_user_company(request.user)

    if request.method == 'POST':
        # Only update the AI-related fields
        ai_enabled = request.POST.get('ai_enabled') == 'on'
        openai_api_key = request.POST.get('openai_api_key', '').strip()
        openai_model = request.POST.get('openai_model', '').strip() or 'gpt-4o-mini'

        company.ai_enabled = ai_enabled
        company.openai_model = openai_model
        # Only overwrite the key if the user actually typed something new
        # (the form shows a password field, so it comes back empty when unchanged)
        if openai_api_key:
            company.openai_api_key = openai_api_key
        company.save(update_fields=['ai_enabled', 'openai_api_key', 'openai_model'])

        messages.success(request, _('AI settings updated successfully.'))
        return redirect('erp:ai_settings')

    context = {
        'title': _('AI Settings'),
        'company': company,
        'has_api_key': bool(company.openai_api_key),
    }
    return render(request, 'erp/ai/settings.html', context)
