"""
Signals for Tenant Management
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import TenantUser, DatabaseAssignment

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TenantUser)
def user_status_changed(sender, instance, created, **kwargs):
    """Handle TenantUser lifecycle events.

    * New registration  → log the event (admins can monitor via log aggregation).
    * Approved          → log the event.
    * Rejected          → log the event and ensure ``is_active=False`` so the
                          account cannot be used.  Uses ``queryset.update()``
                          rather than ``instance.save()`` to avoid triggering
                          this signal recursively.
    """
    if created:
        logger.info(
            "New tenant user registered: email=%s pk=%s",
            instance.email,
            instance.pk,
        )
        return

    if instance.approval_status == "approved" and instance.is_approved:
        logger.info(
            "Tenant user approved: email=%s pk=%s",
            instance.email,
            instance.pk,
        )
    elif instance.approval_status == "rejected":
        logger.info(
            "Tenant user rejected: email=%s pk=%s",
            instance.email,
            instance.pk,
        )
        # Deactivate the account.  Queryset .update() bypasses signal dispatch
        # so this will not recurse.  The .exclude() guard makes it a no-op when
        # already inactive.
        sender.objects.filter(pk=instance.pk).exclude(is_active=False).update(
            is_active=False,
        )


@receiver(post_save, sender=DatabaseAssignment)
def database_assigned(sender, instance, created, **kwargs):
    """Log new database assignments for observability."""
    if created:
        logger.info(
            "DatabaseAssignment created: user_id=%s database_id=%s role=%s active=%s",
            instance.user_id,
            instance.database_id,
            instance.role,
            instance.is_active,
        )
