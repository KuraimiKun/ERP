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
# Export cache invalidation
# ---------------------------------------------------------------------------

# Lazy-built reverse map: Model class → export entity name
_model_to_entity: dict | None = None


def _get_model_entity_map():
    global _model_to_entity
    if _model_to_entity is None:
        from erp.services.export import EXPORT_REGISTRY
        _model_to_entity = {
            cfg['model']: name for name, cfg in EXPORT_REGISTRY.items()
        }
    return _model_to_entity


def _invalidate_export_cache(instance):
    """Bump the generation counter for the entity's export cache."""
    mapping = _get_model_entity_map()
    entity = mapping.get(type(instance))
    if entity is None:
        return
    from erp.services.export import EXPORT_REGISTRY, invalidate_export_cache
    config = EXPORT_REGISTRY[entity]
    if config.get('company_filter', True) is False:
        invalidate_export_cache(entity, 0)
    else:
        company_field = config.get('company_field', 'company')
        # follow FK chain: 'employee__company' → instance.employee.company
        obj = instance
        for attr in company_field.split('__'):
            obj = getattr(obj, attr, None)
            if obj is None:
                return
        invalidate_export_cache(entity, obj.pk if hasattr(obj, 'pk') else obj)

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

    key = (_model_label(instance), instance.pk)
    try:
        old = sender.all_objects.get(pk=instance.pk)
        # Overwrite any stale entry left by a previous failed save so the dict
        # does not accumulate unbounded entries on transaction rollbacks.
        _pre_save_state[key] = old
    except sender.DoesNotExist:
        # Row was deleted between pre_save and here; discard any stale entry.
        _pre_save_state.pop(key, None)


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    """Log a CREATE or UPDATE after the object has been saved."""
    if not _should_audit(instance):
        return

    _invalidate_export_cache(instance)

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

    _invalidate_export_cache(instance)

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
# Finance: keep Invoice totals in sync when lines are edited
# ---------------------------------------------------------------------------

_invoice_line_fields = ['line_total', 'tax_amount', 'quantity', 'unit_price',
                        'discount_percent', 'tax_rate_id']


@receiver(post_save, sender='erp.InvoiceLine')
def sync_invoice_totals_on_line_save(sender, instance, **kwargs):
    """Recalculate parent Invoice totals whenever a line is created or updated.

    InvoiceLine.save() updates line_total and tax_amount on the line itself,
    but the parent Invoice.subtotal / total_amount / balance_due only get
    updated if Invoice.calculate_totals() is explicitly called.  Without this
    signal, editing a line via the API leaves the invoice totals stale.
    """
    from django.db import transaction
    invoice = instance.invoice
    try:
        with transaction.atomic():
            # Re-fetch with a row-lock so concurrent line edits serialise here.
            invoice = invoice.__class__.objects.select_for_update().get(
                pk=invoice.pk
            )
            invoice.calculate_totals()
            invoice.save(update_fields=[
                'subtotal', 'tax_amount', 'total_amount', 'balance_due', 'status'
            ])
    except Exception:
        logger.exception(
            'Failed to sync Invoice pk=%s totals after line save', invoice.pk
        )


@receiver(post_delete, sender='erp.InvoiceLine')
def sync_invoice_totals_on_line_delete(sender, instance, **kwargs):
    """Recalculate parent Invoice totals when a line is deleted."""
    from django.db import transaction
    invoice = instance.invoice
    try:
        with transaction.atomic():
            invoice = invoice.__class__.objects.select_for_update().get(
                pk=invoice.pk
            )
            invoice.calculate_totals()
            invoice.save(update_fields=[
                'subtotal', 'tax_amount', 'total_amount', 'balance_due', 'status'
            ])
    except Exception:
        logger.exception(
            'Failed to sync Invoice pk=%s totals after line delete', invoice.pk
        )


# ---------------------------------------------------------------------------
# Auth signals (login / logout)
# ---------------------------------------------------------------------------

def _auditlog_table_exists():
    """Return True if the erp_auditlog table is present in the current database.

    Uses Django's database-agnostic introspection API instead of raw SQL so
    this works on SQLite, PostgreSQL, MySQL, and Oracle without modification.
    Cached per process — the table set doesn't change after migrations run.
    """
    from django.db import connection
    with connection.cursor() as cursor:
        return 'erp_auditlog' in connection.introspection.table_names(cursor)


@receiver(user_logged_in)
def audit_user_login(sender, request, user, **kwargs):
    """Log when a user logs in."""
    try:
        # Skip if the audit table hasn't been migrated yet (e.g. fresh setup).
        if not _auditlog_table_exists():
            return
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
        if not _auditlog_table_exists():
            return
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
