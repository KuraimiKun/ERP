"""
Context Processors for Tenant Management
"""

from .routers import get_current_db_alias


def tenant_context(request):
    """
    Add tenant-related context to all templates.
    """
    context = {
        'current_db_alias': get_current_db_alias(),
        'is_tenant_context': get_current_db_alias() != 'default',
    }
    
    if request.user.is_authenticated:
        context['user_is_approved'] = request.user.is_approved
        context['user_approval_status'] = request.user.approval_status
        context['user_has_database'] = bool(request.user.assigned_database)
        
        if request.user.assigned_database:
            context['assigned_database'] = request.user.assigned_database
    
    return context
