"""
ERP Services - Audit Service

Provides automatic audit logging for model changes.
"""

import threading

from django.contrib.contenttypes.models import ContentType
from ..models import AuditLog

# Module-level thread-local storage for audit context
_audit_thread_locals = threading.local()


def get_audit_context():
    """Get the current request context stored by AuditMiddleware."""
    return {
        'user': getattr(_audit_thread_locals, 'user', None),
        'ip_address': getattr(_audit_thread_locals, 'ip_address', None),
        'user_agent': getattr(_audit_thread_locals, 'user_agent', ''),
    }


class AuditService:
    """Service for creating audit log entries."""
    
    @staticmethod
    def log_action(user, action, obj, changes=None, ip_address=None, user_agent='', notes=''):
        """
        Create an audit log entry.
        
        Args:
            user: The user performing the action
            action: The action type (create, update, delete, view, etc.)
            obj: The object being acted upon
            changes: Dictionary of field changes (before/after values)
            ip_address: IP address of the request
            user_agent: User agent string
            notes: Additional notes
        
        Returns:
            AuditLog: The created audit log entry
        """
        content_type = ContentType.objects.get_for_model(obj)
        
        return AuditLog.objects.create(
            user=user,
            action=action,
            content_type=content_type,
            object_id=obj.pk,
            object_repr=str(obj)[:255],
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent or '',
            notes=notes
        )
    
    @staticmethod
    def log_create(user, obj, ip_address=None, user_agent=''):
        """Log a create action."""
        return AuditService.log_action(
            user=user,
            action=AuditLog.Action.CREATE,
            obj=obj,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_update(user, obj, changes, ip_address=None, user_agent=''):
        """Log an update action with changes."""
        return AuditService.log_action(
            user=user,
            action=AuditLog.Action.UPDATE,
            obj=obj,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_delete(user, obj, ip_address=None, user_agent=''):
        """Log a delete action."""
        return AuditService.log_action(
            user=user,
            action=AuditLog.Action.DELETE,
            obj=obj,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_view(user, obj, ip_address=None, user_agent=''):
        """Log a view action."""
        return AuditService.log_action(
            user=user,
            action=AuditLog.Action.VIEW,
            obj=obj,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_approve(user, obj, notes='', ip_address=None, user_agent=''):
        """Log an approval action."""
        return AuditService.log_action(
            user=user,
            action=AuditLog.Action.APPROVE,
            obj=obj,
            notes=notes,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_reject(user, obj, notes='', ip_address=None, user_agent=''):
        """Log a rejection action."""
        return AuditService.log_action(
            user=user,
            action=AuditLog.Action.REJECT,
            obj=obj,
            notes=notes,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_login(user, ip_address=None, user_agent=''):
        """Log a login action (without an object)."""
        return AuditLog.objects.create(
            user=user,
            action=AuditLog.Action.LOGIN,
            object_repr=f'User login: {user.email}',
            ip_address=ip_address,
            user_agent=user_agent or ''
        )
    
    @staticmethod
    def log_logout(user, ip_address=None, user_agent=''):
        """Log a logout action (without an object)."""
        return AuditLog.objects.create(
            user=user,
            action=AuditLog.Action.LOGOUT,
            object_repr=f'User logout: {user.email}',
            ip_address=ip_address,
            user_agent=user_agent or ''
        )
    
    @staticmethod
    def get_object_history(obj, limit=50):
        """
        Get audit history for an object.
        
        Args:
            obj: The object to get history for
            limit: Maximum number of entries to return
        
        Returns:
            QuerySet: Audit log entries for the object
        """
        content_type = ContentType.objects.get_for_model(obj)
        return AuditLog.objects.filter(
            content_type=content_type,
            object_id=obj.pk
        ).order_by('-created_at')[:limit]
    
    @staticmethod
    def get_user_actions(user, limit=100):
        """
        Get recent actions by a user.
        
        Args:
            user: The user to get actions for
            limit: Maximum number of entries to return
        
        Returns:
            QuerySet: Audit log entries by the user
        """
        return AuditLog.objects.filter(
            user=user
        ).order_by('-created_at')[:limit]


def get_field_changes(instance, old_instance):
    """
    Compare two model instances and return the field changes.
    
    Args:
        instance: The new/updated instance
        old_instance: The previous instance state
    
    Returns:
        dict: Dictionary of changed fields with before/after values
    """
    changes = {}
    
    if old_instance is None:
        return changes
    
    for field in instance._meta.fields:
        field_name = field.name
        
        # Skip auto-updated fields
        if field_name in ['updated_at', 'created_at']:
            continue
        
        old_value = getattr(old_instance, field_name, None)
        new_value = getattr(instance, field_name, None)
        
        # Convert to comparable types
        if hasattr(old_value, 'pk'):
            old_value = old_value.pk
        if hasattr(new_value, 'pk'):
            new_value = new_value.pk
        
        if old_value != new_value:
            changes[field_name] = {
                'before': str(old_value) if old_value is not None else None,
                'after': str(new_value) if new_value is not None else None
            }
    
    return changes


class AuditMiddleware:
    """
    Middleware to capture request information for audit logging.
    Stores user, IP address, and user agent in thread-local storage.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store request info in module-level thread-local storage
        _audit_thread_locals.user = getattr(request, 'user', None)
        _audit_thread_locals.ip_address = self.get_client_ip(request)
        _audit_thread_locals.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        response = self.get_response(request)
        
        return response
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
