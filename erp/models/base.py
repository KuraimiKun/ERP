"""
Base models and mixins for the ERP system.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base model with created and updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditMixin(models.Model):
    """Mixin for tracking who created/modified records."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_created"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_updated"
    )

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted records by default."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def all_with_deleted(self):
        """Return all records including soft-deleted ones."""
        return super().get_queryset()

    def deleted_only(self):
        """Return only soft-deleted records."""
        return super().get_queryset().filter(is_deleted=True)


class SoftDeleteMixin(models.Model):
    """Mixin for soft delete functionality."""

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_deleted"
    )

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        """Soft delete the record."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()


class ERPBaseModel(TimeStampedModel, AuditMixin, SoftDeleteMixin):
    """Base model for all ERP entities combining all mixins."""

    # Use the soft delete manager
    objects = SoftDeleteManager()
    all_objects = models.Manager()  # Includes deleted records

    class Meta:
        abstract = True
