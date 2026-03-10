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


# Models that must ALWAYS go to the default database regardless of context
# (these manage the multi-tenant infrastructure itself)
ALWAYS_DEFAULT_MODELS = {
    'tenants.postgresserver',
    'tenants.tenantdatabase',
    'tenants.databaseassignment',
    'tenants.serverlog',
    'sessions.session',
    'admin.logentry',
}

# Apps that are ALWAYS routed to default (infrastructure only)
ALWAYS_DEFAULT_APPS = {
    'sessions',
    'admin',
}

# Models/apps that exist in BOTH default and tenant DBs (shared apps).
# When a tenant context is active these should be read/written on the
# tenant DB so that FK subqueries against ERP tables work correctly.
SHARED_APPS = {'auth', 'contenttypes', 'tenants', 'authtoken'}


class TenantDatabaseRouter:
    """
    Database router for multi-tenant architecture.
    
    Routes queries to the appropriate database based on:
    1. Model type (infrastructure-only vs shared vs ERP)
    2. Current request context (tenant DB alias in thread-local)

    Infrastructure models (servers, databases, assignments, logs, sessions,
    admin log entries) always go to 'default'.

    Shared models (auth, contenttypes, tenants.TenantUser) exist in both
    default and tenant databases.  When a tenant context is active they are
    routed to the *tenant* DB so that FK subqueries against ERP tables work.

    ERP models only exist in tenant databases.
    """
    
    def _get_model_key(self, model):
        """Get a lowercase model key for comparison."""
        return f"{model._meta.app_label}.{model._meta.model_name}"
    
    def _is_always_default(self, model):
        """True for infrastructure models that must stay on the default DB."""
        model_key = self._get_model_key(model)
        return (
            model_key in ALWAYS_DEFAULT_MODELS or
            model._meta.app_label in ALWAYS_DEFAULT_APPS
        )

    def _is_shared(self, model):
        """True for models whose tables exist in both default and tenant DBs."""
        return model._meta.app_label in SHARED_APPS

    def _route(self, model):
        """Common routing logic for reads and writes."""
        # Infrastructure → always default
        if self._is_always_default(model):
            return 'default'

        # Shared apps: use tenant DB when a tenant context is active
        if self._is_shared(model):
            db_alias = get_current_db_alias()
            if db_alias != 'default' and db_alias in settings.DATABASES:
                return db_alias
            return 'default'

        # ERP models → tenant DB
        db_alias = get_current_db_alias()
        if db_alias in settings.DATABASES:
            return db_alias
        return 'default'

    def db_for_read(self, model, **hints):
        return self._route(model)
    
    def db_for_write(self, model, **hints):
        return self._route(model)
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects.

        Because shared apps (auth, contenttypes, tenants) are migrated to
        *both* the default and tenant databases, their records can coexist
        with ERP records on the same tenant DB.  We therefore allow all
        relations — Django's FK integrity is enforced at the DB level anyway.
        """
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Control which databases receive migrations for which models.
        
        - ERP app: tenant databases only (not default)
        - auth, contenttypes, tenants: BOTH default AND tenant databases
          (tenant DBs need these tables for FK constraints from ERP models)
        - sessions, admin: default only
        """
        # Apps whose tables are needed in tenant databases for FK support
        SHARED_APPS = {'auth', 'contenttypes', 'tenants', 'authtoken'}

        if app_label in SHARED_APPS:
            # These apps migrate to both default and tenant databases
            return True

        # ERP app (and its sub-apps like erp_ai) migrates to tenant databases only
        if app_label in {'erp', 'erp_ai'}:
            if db == 'default':
                return False
            return True
        
        # Everything else (sessions, admin, etc.) -> default only
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
    
    Also closes / removes any stale cached connection so Django creates
    a fresh DatabaseWrapper with the current config (including keys like
    DISABLE_SERVER_SIDE_CURSORS).
    
    Args:
        tenant_db: TenantDatabase instance
        
    Returns:
        str: The database alias that was added
    """
    from django.db import connections

    db_alias = f"tenant_{tenant_db.id}"
    new_config = tenant_db.connection_config
    settings.DATABASES[db_alias] = new_config

    # If a cached DatabaseWrapper already exists for this alias, close its
    # underlying connection and remove the wrapper from the cache so the
    # next access creates a new wrapper with *new_config*.
    if hasattr(connections, '_connections'):
        old = getattr(connections._connections, db_alias, None)
        if old is not None:
            try:
                old.close()
            except Exception:
                pass
            delattr(connections._connections, db_alias)

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
