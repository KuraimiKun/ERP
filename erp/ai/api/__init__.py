"""
AI API Serializers for the ERP AI module.
"""

from rest_framework import serializers
from erp.ai.models import MLModel, PredictionLog, AIInsight


class MLModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLModel
        fields = [
            'id', 'name', 'model_type', 'version', 'is_active',
            'accuracy_score', 'training_samples', 'last_trained_at',
            'parameters', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PredictionLogSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='model.name', read_only=True)

    class Meta:
        model = PredictionLog
        fields = [
            'id', 'model', 'model_name', 'entity_type', 'entity_id',
            'score', 'details', 'actual_outcome', 'created_at',
        ]
        read_only_fields = fields


class AIInsightSerializer(serializers.ModelSerializer):
    dismissed_by_name = serializers.CharField(
        source='dismissed_by.get_full_name', read_only=True, default='',
    )

    class Meta:
        model = AIInsight
        fields = [
            'id', 'category', 'severity', 'title', 'description',
            'recommendation', 'entity_type', 'entity_id', 'action_url',
            'is_dismissed', 'dismissed_by_name', 'dismissed_at',
            'created_at',
        ]
        read_only_fields = [
            'id', 'category', 'severity', 'title', 'description',
            'recommendation', 'entity_type', 'entity_id', 'action_url',
            'dismissed_by_name', 'dismissed_at', 'created_at',
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
    message = serializers.CharField(default='')
