"""
Audit and System Configuration models for the ERP system.
"""

import json

from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from .base import TimeStampedModel

# Maximum file size for any single attachment (10 MB)
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

# Allowed file extensions for attachments.  Executables and server-side
# scripts are intentionally excluded regardless of content-type header.
_ALLOWED_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "xlsx",
    "xls",
    "csv",
    "docx",
    "doc",
    "txt",
    "zip",
}


class AuditLog(TimeStampedModel):
    """Audit trail for all changes in the system."""

    class Action(models.TextChoices):
        CREATE = "create", "Created"
        UPDATE = "update", "Updated"
        DELETE = "delete", "Deleted"
        VIEW = "view", "Viewed"
        EXPORT = "export", "Exported"
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        APPROVE = "approve", "Approved"
        REJECT = "reject", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="erp_audit_logs"
    )

    action = models.CharField(max_length=20, choices=Action.choices)

    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # Object representation
    object_repr = models.CharField(max_length=255, blank=True)

    # Changes
    changes = models.JSONField(default=dict, blank=True, help_text=_("Before/after values"))

    # Request info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Additional context
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = "Audit Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user} {self.action} {self.object_repr}"


class SystemSetting(TimeStampedModel):
    """System-wide configuration settings."""

    class SettingType(models.TextChoices):
        STRING = "string", "String"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        BOOLEAN = "boolean", "Boolean"
        JSON = "json", "JSON"
        TEXT = "text", "Text"

    company = models.ForeignKey("erp.Company", on_delete=models.CASCADE, related_name="system_settings")

    key = models.CharField(max_length=100)
    value = models.TextField()
    setting_type = models.CharField(max_length=20, choices=SettingType.choices, default=SettingType.STRING)

    category = models.CharField(max_length=100, blank=True, help_text=_("Setting category for grouping"))
    description = models.TextField(blank=True)

    is_encrypted = models.BooleanField(default=False)
    is_editable = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("System Setting")
        verbose_name_plural = "System Settings"
        unique_together = ["company", "key"]
        ordering = ["category", "key"]

    def __str__(self):
        return f"{self.key}"

    def get_value(self):
        """Get typed value."""
        if self.setting_type == self.SettingType.INTEGER:
            return int(self.value)
        elif self.setting_type == self.SettingType.DECIMAL:
            from decimal import Decimal

            return Decimal(self.value)
        elif self.setting_type == self.SettingType.BOOLEAN:
            return self.value.lower() in ("true", "1", "yes")
        elif self.setting_type == self.SettingType.JSON:
            return json.loads(self.value)
        return self.value


class Notification(TimeStampedModel):
    """System notifications for users."""

    class NotificationType(models.TextChoices):
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        TASK = "task", "Task"
        REMINDER = "reminder", "Reminder"
        APPROVAL = "approval", "Approval Required"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="erp_notifications")

    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.INFO)
    title = models.CharField(max_length=255)
    message = models.TextField()

    # Link to related object
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    # URL for action
    action_url = models.CharField(max_length=500, blank=True)

    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Email notification
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient}"


class EmailTemplate(TimeStampedModel):
    """Email templates for system communications."""

    company = models.ForeignKey("erp.Company", on_delete=models.CASCADE, related_name="email_templates")

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, help_text=_("Unique template identifier"))
    subject = models.CharField(max_length=255)

    # Content
    body_html = models.TextField(help_text=_("HTML content with placeholders"))
    body_text = models.TextField(blank=True, help_text=_("Plain text fallback"))

    # Available placeholders
    available_placeholders = models.JSONField(
        default=list, blank=True, help_text=_("List of available placeholder variables")
    )

    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Email Template")
        verbose_name_plural = "Email Templates"
        unique_together = ["company", "code"]
        ordering = ["name"]

    def __str__(self):
        return self.name


class FileAttachment(TimeStampedModel):
    """Generic file attachments for any model."""

    def attachment_path(instance, filename):
        import secrets

        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        # Use a cryptographically random name so stored filenames are not
        # guessable even if the storage bucket is misconfigured as public.
        new_filename = f"{secrets.token_urlsafe(32)}.{ext}"
        return f"erp/attachments/{instance.content_type.model}/{new_filename}"

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="erp_file_uploads"
    )

    # Generic relation
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    file = models.FileField(upload_to="erp/attachments/")
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)

    description = models.TextField(blank=True)

    class Meta:
        verbose_name = _("File Attachment")
        verbose_name_plural = "File Attachments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return self.original_filename

    def clean(self):
        if self.file:
            # Enforce size limit
            size = getattr(self.file, "size", 0)
            if size > _MAX_ATTACHMENT_BYTES:
                raise ValidationError(
                    f"File size {size // (1024 * 1024)} MB exceeds the "
                    f"{_MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB limit."
                )
            # Enforce extension whitelist (uses the original name, not the
            # UUID-renamed storage path, to catch .php → .pdf renames).
            name = self.original_filename or getattr(self.file, "name", "")
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in _ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f'File type ".{ext}" is not allowed. Permitted types: {", ".join(sorted(_ALLOWED_EXTENSIONS))}.'
                )

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = self.file.name
        if self.file:
            self.file_size = self.file.size
        # Validation is enforced via clean() which Django forms call automatically.
        # Calling full_clean() here would double-validate on form submissions and
        # also run validators that require a DB hit before the row is committed.
        super().save(*args, **kwargs)


class ScheduledTask(TimeStampedModel):
    """Scheduled background tasks."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey("erp.Company", on_delete=models.CASCADE, related_name="scheduled_tasks")

    name = models.CharField(max_length=255)
    task_type = models.CharField(max_length=100)

    # Schedule
    cron_expression = models.CharField(max_length=100, blank=True, help_text=_("Cron expression for recurring tasks"))
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text=_("One-time execution"))

    # Parameters
    parameters = models.JSONField(default=dict, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)

    # Results
    last_result = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    is_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Scheduled Task")
        verbose_name_plural = "Scheduled Tasks"
        ordering = ["next_run"]

    def __str__(self):
        return self.name


class IntegrationLog(TimeStampedModel):
    """Log for external integrations."""

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        PENDING = "pending", "Pending"

    company = models.ForeignKey("erp.Company", on_delete=models.CASCADE, related_name="integration_logs")

    integration_name = models.CharField(max_length=100)
    direction = models.CharField(max_length=10, choices=Direction.choices)

    # Request/Response
    endpoint = models.CharField(max_length=500, blank=True)
    method = models.CharField(max_length=10, blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=Status.choices)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Timing
    duration_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("Integration Log")
        verbose_name_plural = "Integration Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "integration_name", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.integration_name} - {self.status}"
