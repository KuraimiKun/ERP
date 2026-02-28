"""
ERP Signals – Automatic Audit Logging

Connects Django model signals to the AuditService so that every create,
update, and delete on audited models is recorded in the AuditLog table
automatically.  Login / logout events are captured via Django's built-in
auth signals.

The middleware ``erp.services.audit.AuditMiddleware`` must be active so
that the current request context (user, IP, user-agent) is available in
thread-local storage.
"""

import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from erp.models.base import ERPBaseModel
from erp.services.audit import AuditService, get_audit_context, get_field_changes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Cache for old instance state (keyed by (model_label, pk))
_pre_save_state: dict = {}


def _model_label(instance):
    return instance._meta.label


def _should_audit(instance):
    """Return True if *instance* should be audited.

    We audit everything that inherits from ERPBaseModel **except**
    AuditLog itself (to avoid infinite recursion).
    """
    from erp.models import AuditLog
    if isinstance(instance, AuditLog):
        return False
    return isinstance(instance, ERPBaseModel)


# ---------------------------------------------------------------------------
# Model signals
# ---------------------------------------------------------------------------

@receiver(pre_save)
def audit_pre_save(sender, instance, **kwargs):
    """Capture the old state of an object before it is saved."""
    if not _should_audit(instance):
        return
    if instance.pk is None:
        return  # new object – nothing to compare against

    try:
        old = sender.all_objects.get(pk=instance.pk)
        _pre_save_state[(_model_label(instance), instance.pk)] = old
    except sender.DoesNotExist:
        pass


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    """Log a CREATE or UPDATE after the object has been saved."""
    if not _should_audit(instance):
        return

    ctx = get_audit_context()
    user = ctx.get('user')
    if user is None or (hasattr(user, 'is_authenticated') and not user.is_authenticated):
        return  # skip anonymous / system saves

    try:
        if created:
            AuditService.log_create(
                user=user,
                obj=instance,
                ip_address=ctx.get('ip_address'),
                user_agent=ctx.get('user_agent', ''),
            )
        else:
            key = (_model_label(instance), instance.pk)
            old_instance = _pre_save_state.pop(key, None)
            changes = get_field_changes(instance, old_instance)
            if changes:  # only log if something actually changed
                AuditService.log_update(
                    user=user,
                    obj=instance,
                    changes=changes,
                    ip_address=ctx.get('ip_address'),
                    user_agent=ctx.get('user_agent', ''),
                )
    except Exception:
        logger.exception('Failed to write audit log for %s pk=%s', sender.__name__, instance.pk)


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    """Log a DELETE when an object is removed."""
    if not _should_audit(instance):
        return

    ctx = get_audit_context()
    user = ctx.get('user')
    if user is None or (hasattr(user, 'is_authenticated') and not user.is_authenticated):
        return

    try:
        AuditService.log_delete(
            user=user,
            obj=instance,
            ip_address=ctx.get('ip_address'),
            user_agent=ctx.get('user_agent', ''),
        )
    except Exception:
        logger.exception('Failed to write audit delete log for %s pk=%s', sender.__name__, instance.pk)


# ---------------------------------------------------------------------------
# Auth signals (login / logout)
# ---------------------------------------------------------------------------

@receiver(user_logged_in)
def audit_user_login(sender, request, user, **kwargs):
    """Log when a user logs in."""
    try:
        ip = _get_client_ip(request) if request else None
        ua = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''
        AuditService.log_login(user=user, ip_address=ip, user_agent=ua)
    except Exception:
        logger.exception('Failed to write login audit log for user %s', user)


@receiver(user_logged_out)
def audit_user_logout(sender, request, user, **kwargs):
    """Log when a user logs out."""
    if user is None:
        return
    try:
        ip = _get_client_ip(request) if request else None
        ua = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''
        AuditService.log_logout(user=user, ip_address=ip, user_agent=ua)
    except Exception:
        logger.exception('Failed to write logout audit log for user %s', user)


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
