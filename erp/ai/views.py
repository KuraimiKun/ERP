"""
AI Dashboard Views – server-rendered views for the AI insights dashboard.
"""

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _

from erp.decorators import tenant_required
from erp.views._common import get_user_company, paginate_qs
from erp.ai.models import MLModel, PredictionLog, AIInsight, ExplanationResult


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


# ══════════════════════════════════════════════════════════════════════════════
#  Explainable AI (XAI) Views
# ══════════════════════════════════════════════════════════════════════════════

# Models that support XAI explanations
XAI_MODELS = {
    'late_payment': {'entity_type': 'Invoice', 'label': 'Late Payment Prediction'},
    'lead_scoring': {'entity_type': 'Lead', 'label': 'Lead Scoring'},
    'attrition': {'entity_type': 'Employee', 'label': 'Employee Attrition'},
    'expense_anomaly': {'entity_type': 'Expense', 'label': 'Expense Anomaly Detection'},
}


@login_required
@tenant_required
def xai_dashboard(request):
    """Explainable AI overview – lists available models and recent explanations."""
    company = get_user_company(request.user)

    # Trained models that support XAI — annotate explanation counts in one query
    models = MLModel.objects.filter(
        company=company, is_active=True,
        model_type__in=XAI_MODELS,
    ).annotate(explanation_count=Count('explanations')).order_by('model_type')

    model_cards = []
    for m in models:
        info = XAI_MODELS.get(m.model_type, {})
        model_cards.append({
            'model': m,
            'entity_type': info.get('entity_type', ''),
            'label': info.get('label', m.name),
            'explanation_count': m.explanation_count,
        })

    recent = ExplanationResult.objects.filter(
        model__company=company,
    ).select_related('model').order_by('-created_at')[:10]

    context = {
        'title': _('Explainable AI'),
        'model_cards': model_cards,
        'recent_explanations': recent,
        'xai_models': XAI_MODELS,
    }
    return render(request, 'erp/ai/xai_dashboard.html', context)


@login_required
@tenant_required
def xai_explain(request):
    """Generate or view an individual XAI explanation."""
    company = get_user_company(request.user)
    result = None
    error = None

    if request.method == 'POST':
        model_type = request.POST.get('model_type', '')
        entity_id = request.POST.get('entity_id', '')
        method = request.POST.get('method', 'shap')

        if model_type not in XAI_MODELS:
            error = _('Invalid model type selected.')
        elif not entity_id or not entity_id.isdigit():
            error = _('Please enter a valid entity ID.')
        else:
            from erp.ai.services.explainability import ExplainabilityService
            svc = ExplainabilityService(company)
            entity_type = XAI_MODELS[model_type]['entity_type']
            result = svc.explain_prediction(
                model_type=model_type,
                entity_type=entity_type,
                entity_id=int(entity_id),
                method=method,
            )
            if 'error' in result:
                error = result['error']
                result = None

    context = {
        'title': _('Explain Prediction'),
        'xai_models': XAI_MODELS,
        'result': result,
        'error': error,
        'selected_model': request.POST.get('model_type', ''),
        'selected_entity': request.POST.get('entity_id', ''),
        'selected_method': request.POST.get('method', 'shap'),
    }
    return render(request, 'erp/ai/xai_explain.html', context)


@login_required
@tenant_required
def xai_global(request, model_type):
    """Global feature importance for a model type."""
    company = get_user_company(request.user)

    if model_type not in XAI_MODELS:
        messages.error(request, _('Invalid model type.'))
        return redirect('erp:xai_dashboard')

    from erp.ai.services.explainability import ExplainabilityService
    svc = ExplainabilityService(company)
    result = svc.global_feature_importance(model_type)

    context = {
        'title': _('Global Feature Importance – %(label)s') % {
            'label': XAI_MODELS[model_type]['label'],
        },
        'model_type': model_type,
        'model_label': XAI_MODELS[model_type]['label'],
        'result': result,
        'has_error': 'error' in result,
    }
    return render(request, 'erp/ai/xai_global.html', context)


@login_required
@tenant_required
def xai_history(request):
    """Paginated list of all stored explanations."""
    company = get_user_company(request.user)
    qs = ExplanationResult.objects.filter(
        model__company=company,
    ).select_related('model').order_by('-created_at')

    model_type = request.GET.get('model_type')
    method = request.GET.get('method')
    if model_type:
        qs = qs.filter(model__model_type=model_type)
    if method:
        qs = qs.filter(method=method)

    page_obj = paginate_qs(request, qs, per_page=25)
    context = {
        'title': _('Explanation History'),
        'page_obj': page_obj,
        'xai_models': XAI_MODELS,
        'selected_model_type': model_type,
        'selected_method': method,
    }
    return render(request, 'erp/ai/xai_history.html', context)
