from django.contrib import admin
from .models import MLModel, PredictionLog, AIInsight
from erp.admin.mixins import CompanyIsolatedAdmin


@admin.register(MLModel)
class MLModelAdmin(CompanyIsolatedAdmin):
    list_display = ('name', 'model_type', 'company', 'version', 'is_active',
                    'accuracy_score', 'last_trained_at')
    list_filter = ('model_type', 'is_active', 'company')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'last_trained_at',
                       'training_samples', 'accuracy_score')


@admin.register(PredictionLog)
class PredictionLogAdmin(CompanyIsolatedAdmin):
    company_lookup = 'model__company'
    list_display = ('model', 'entity_type', 'entity_id', 'score',
                    'created_at')
    list_filter = ('model__model_type', 'entity_type')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(AIInsight)
class AIInsightAdmin(CompanyIsolatedAdmin):
    list_display = ('company', 'category', 'severity', 'title',
                    'is_dismissed', 'created_at')
    list_filter = ('category', 'severity', 'is_dismissed')
    search_fields = ('title', 'description')
    date_hierarchy = 'created_at'
