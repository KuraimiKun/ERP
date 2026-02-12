"""
Multi-Tenant Database Router

This router directs database operations to the appropriate database:
- Tenant management models -> default database
- ERP models -> tenant-specific database

The tenant database is determined from the current request context.
"""

import threading
from django.conf import settings

# Thread-local storage for current tenant database
_thread_locals = threading.local()


def get_current_db_alias():
    """Get the current tenant database alias from thread-local storage."""
    return getattr(_thread_locals, 'db_alias', 'default')


def set_current_db_alias(db_alias):
    """Set the current tenant database alias in thread-local storage."""
    _thread_locals.db_alias = db_alias


def clear_current_db_alias():
    """Clear the current tenant database alias."""
    if hasattr(_thread_locals, 'db_alias'):
        del _thread_locals.db_alias


# Models that should always use the default database
TENANT_MANAGEMENT_MODELS = {
    'tenants.tenantuser',
    'tenants.postgresserver',
    'tenants.tenantdatabase',
    'tenants.databaseassignment',
    'tenants.serverlog',
    'auth.permission',
    'auth.group',
    'contenttypes.contenttype',
    'sessions.session',
    'admin.logentry',
}

# Apps that should use the default database
TENANT_MANAGEMENT_APPS = {
    'auth',
    'contenttypes',
    'sessions',
    'admin',
    'tenants',
}


class TenantDatabaseRouter:
    """
    Database router for multi-tenant architecture.
    
    Routes queries to the appropriate database based on:
    1. Model type (tenant management vs ERP)
    2. Current request context
    """
    
    def _get_model_key(self, model):
        """Get a lowercase model key for comparison."""
        return f"{model._meta.app_label}.{model._meta.model_name}"
    
    def _is_tenant_management_model(self, model):
        """Check if the model belongs to tenant management."""
        model_key = self._get_model_key(model)
        return (
            model_key in TENANT_MANAGEMENT_MODELS or
            model._meta.app_label in TENANT_MANAGEMENT_APPS
        )
    
    def db_for_read(self, model, **hints):
        """
        Route read operations to the appropriate database.
        """
        if self._is_tenant_management_model(model):
            return 'default'
        
        # Use the tenant database from thread-local storage
        db_alias = get_current_db_alias()
        
        # Verify the database exists in settings
        if db_alias in settings.DATABASES:
            return db_alias
        
        return 'default'
    
    def db_for_write(self, model, **hints):
        """
        Route write operations to the appropriate database.
        """
        if self._is_tenant_management_model(model):
            return 'default'
        
        db_alias = get_current_db_alias()
        
        if db_alias in settings.DATABASES:
            return db_alias
        
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if both objects are in the same database group.
        """
        # Get the model keys
        model1_key = self._get_model_key(obj1.__class__)
        model2_key = self._get_model_key(obj2.__class__)
        
        # Both tenant management models
        is_mgmt1 = self._is_tenant_management_model(obj1.__class__)
        is_mgmt2 = self._is_tenant_management_model(obj2.__class__)
        
        if is_mgmt1 and is_mgmt2:
            return True
        
        # Both ERP models
        if not is_mgmt1 and not is_mgmt2:
            return True
        
        # Cross-database relations are not allowed
        return False
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Control which databases receive migrations for which models.
        """
        # Tenant management apps only migrate to default
        if app_label in TENANT_MANAGEMENT_APPS:
            return db == 'default'
        
        # ERP app migrates to all databases except default
        if app_label == 'erp':
            # For the default database, don't migrate ERP models
            if db == 'default':
                return False
            # For tenant databases, allow ERP migrations
            return True
        
        # For any other apps, use default database
        return db == 'default'


class TenantDatabaseContext:
    """
    Context manager for temporarily switching the tenant database.
    
    Usage:
        with TenantDatabaseContext('tenant_db_alias'):
            # All queries here will use tenant_db_alias database
            MyModel.objects.all()
    """
    
    def __init__(self, db_alias):
        self.db_alias = db_alias
        self.previous_alias = None
    
    def __enter__(self):
        self.previous_alias = get_current_db_alias()
        set_current_db_alias(self.db_alias)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.previous_alias:
            set_current_db_alias(self.previous_alias)
        else:
            clear_current_db_alias()
        return False


def add_tenant_database(tenant_db):
    """
    Dynamically add a tenant database to Django's DATABASES setting.
    
    Args:
        tenant_db: TenantDatabase instance
        
    Returns:
        str: The database alias that was added
    """
    db_alias = f"tenant_{tenant_db.id}"
    
    settings.DATABASES[db_alias] = tenant_db.connection_config
    
    return db_alias


def remove_tenant_database(tenant_db):
    """
    Remove a tenant database from Django's DATABASES setting.
    
    Args:
        tenant_db: TenantDatabase instance or database alias string
    """
    if isinstance(tenant_db, str):
        db_alias = tenant_db
    else:
        db_alias = f"tenant_{tenant_db.id}"
    
    if db_alias in settings.DATABASES and db_alias != 'default':
        del settings.DATABASES[db_alias]


def get_tenant_db_alias(user):
    """
    Get the database alias for a user's assigned tenant database.
    
    Args:
        user: TenantUser instance
        
    Returns:
        str: Database alias or 'default' if no assignment
    """
    if not user or not user.is_authenticated or not user.is_approved:
        return 'default'
    
    # Get active database assignment
    assignment = user.database_assignments.filter(is_active=True).first()
    
    if not assignment or not assignment.database:
        return 'default'
    
    tenant_db = assignment.database
    
    if tenant_db.status != 'active':
        return 'default'
    
    # Ensure the database is in settings
    db_alias = f"tenant_{tenant_db.id}"
    
    if db_alias not in settings.DATABASES:
        add_tenant_database(tenant_db)
    
    return db_alias
