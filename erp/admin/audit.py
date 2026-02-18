"""
ERP Admin – Audit & System models
"""

from django.contrib import admin
from erp.models import (
    AuditLog, SystemSetting, Notification, EmailTemplate,
    FileAttachment, ScheduledTask, IntegrationLog,
)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'object_repr', 'ip_address']
    list_filter = ['action', 'created_at']
    search_fields = ['user__email', 'object_repr']
    date_hierarchy = 'created_at'
    readonly_fields = [
        'user', 'action', 'content_type', 'object_id', 'object_repr',
        'changes', 'ip_address', 'user_agent', 'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'category', 'setting_type', 'is_editable']
    list_filter = ['company', 'category', 'setting_type']
    search_fields = ['key', 'category']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']
    search_fields = ['title', 'recipient__email']
    date_hierarchy = 'created_at'


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'subject', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['name', 'code', 'subject']


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'task_type', 'status', 'last_run', 'next_run', 'is_enabled']
    list_filter = ['status', 'is_enabled']
    search_fields = ['name', 'task_type']


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ['integration_name', 'direction', 'status', 'status_code', 'duration_ms', 'created_at']
    list_filter = ['integration_name', 'direction', 'status']
    date_hierarchy = 'created_at'
    readonly_fields = [
        'integration_name', 'direction', 'endpoint', 'method',
        'request_data', 'response_data', 'status', 'status_code',
        'error_message', 'duration_ms', 'created_at',
    ]
