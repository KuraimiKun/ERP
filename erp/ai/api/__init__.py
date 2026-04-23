"""
AI API Serializers for the ERP AI module.
"""

from rest_framework import serializers
from erp.ai.models import (
    MLModel,
    PredictionLog,
    AIInsight,
    ExplanationResult,
    AITrainingRun,
)


class MLModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLModel
        fields = [
            "id",
            "name",
            "model_type",
            "version",
            "is_active",
            "accuracy_score",
            "training_samples",
            "last_trained_at",
            "parameters",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PredictionLogSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.name", read_only=True)

    class Meta:
        model = PredictionLog
        fields = [
            "id",
            "model",
            "model_name",
            "entity_type",
            "entity_id",
            "score",
            "details",
            "actual_outcome",
            "created_at",
        ]
        read_only_fields = fields


class AIInsightSerializer(serializers.ModelSerializer):
    dismissed_by_name = serializers.CharField(
        source="dismissed_by.get_full_name",
        read_only=True,
        default="",
    )

    class Meta:
        model = AIInsight
        fields = [
            "id",
            "category",
            "severity",
            "title",
            "description",
            "recommendation",
            "entity_type",
            "entity_id",
            "action_url",
            "is_dismissed",
            "dismissed_by_name",
            "dismissed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "category",
            "severity",
            "title",
            "description",
            "recommendation",
            "entity_type",
            "entity_id",
            "action_url",
            "dismissed_by_name",
            "dismissed_at",
            "created_at",
        ]


class AssistantQuerySerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000)


class AssistantResponseSerializer(serializers.Serializer):
    answer = serializers.JSONField()
    code = serializers.CharField()
    error = serializers.CharField(allow_null=True)


class TriggerResultSerializer(serializers.Serializer):
    status = serializers.CharField()
    results = serializers.ListField(child=serializers.DictField(), default=[])
    message = serializers.CharField(default="")


class ExplanationResultSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.name", read_only=True)
    model_type = serializers.CharField(source="model.model_type", read_only=True)
    method_display = serializers.CharField(
        source="get_method_display",
        read_only=True,
    )

    class Meta:
        model = ExplanationResult
        fields = [
            "id",
            "model",
            "model_name",
            "model_type",
            "entity_type",
            "entity_id",
            "method",
            "method_display",
            "prediction_score",
            "base_value",
            "contributions",
            "top_features",
            "waterfall_data",
            "created_at",
        ]
        read_only_fields = fields


class ExplainRequestSerializer(serializers.Serializer):
    model_type = serializers.ChoiceField(choices=MLModel.ModelType.choices)
    entity_type = serializers.CharField(max_length=50)
    entity_id = serializers.IntegerField(min_value=1)
    method = serializers.ChoiceField(
        choices=[("shap", "SHAP"), ("lime", "LIME")],
        default="shap",
    )


class AITrainingRunSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.SerializerMethodField()
    run_type_display = serializers.CharField(
        source="get_run_type_display",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    progress_pct = serializers.SerializerMethodField()

    class Meta:
        model = AITrainingRun
        fields = [
            "id",
            "run_type",
            "run_type_display",
            "status",
            "status_display",
            "evaluate",
            "requested_by_name",
            "started_at",
            "finished_at",
            "duration_seconds",
            "summary_message",
            "error_message",
            "results",
            "progress_step",
            "progress_total",
            "progress_label",
            "progress_pct",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_requested_by_name(self, obj):
        if not obj.requested_by:
            return ""
        full_name = obj.requested_by.get_full_name()
        if full_name:
            return full_name
        return getattr(obj.requested_by, "username", "")

    def get_progress_pct(self, obj):
        if obj.progress_total and obj.progress_total > 0:
            return round(obj.progress_step / obj.progress_total * 100)
        return None
