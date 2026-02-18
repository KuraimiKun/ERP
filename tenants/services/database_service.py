"""
Database Service

Handles database creation, migration, and management for tenant databases.
"""

import logging
import psycopg2
from psycopg2 import sql
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from io import StringIO

from ..routers import add_tenant_database, TenantDatabaseContext

logger = logging.getLogger(__name__)


def sync_user_to_tenant_db(user, db_alias):
    """
    Ensure a TenantUser record exists in the given tenant database.

    ERP models have FK references to AUTH_USER_MODEL.  Because the
    tenants app is migrated to tenant databases (so the table exists),
    the FK constraint requires the referenced row to be present.
    This helper copies the minimal user record if it is missing.
    """
    from ..models import TenantUser

    if TenantUser.objects.using(db_alias).filter(pk=user.pk).exists():
        return  # already synced

    # Build a copy with the same PK so FK values stay consistent
    TenantUser.objects.using(db_alias).create(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        company_name=getattr(user, 'company_name', ''),
        phone=getattr(user, 'phone', ''),
        password=user.password,          # hashed – not used for login here
        is_active=user.is_active,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
        is_approved=getattr(user, 'is_approved', True),
        approval_status=getattr(user, 'approval_status', 'approved'),
    )
    logger.info(f"Synced user {user.email} to tenant DB {db_alias}")


class DatabaseService:
    """
    Service for managing tenant databases.
    
    Handles:
    - Creating databases on PostgreSQL servers
    - Running Django migrations on tenant databases
    - Health checks and status monitoring
    """
    
    def get_admin_connection(self, server, database='postgres'):
        """
        Get a connection to the PostgreSQL server using admin credentials.
        
        Args:
            server: PostgresServer instance
            database: Database to connect to
            
        Returns:
            psycopg2 connection
        """
        return psycopg2.connect(
            host=server.host,
            port=server.port,
            user=server.admin_username,
            password=server.admin_password,
            database=database,
            connect_timeout=10
        )
    
    def check_server_health(self, server):
        """
        Check if a PostgreSQL server is healthy and accessible.
        
        Args:
            server: PostgresServer instance
            
        Returns:
            tuple: (is_healthy, message)
        """
        from ..models import ServerLog
        
        try:
            conn = self.get_admin_connection(server)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            # Update server status
            server.status = 'active'
            server.last_health_check = timezone.now()
            server.health_check_message = f"Healthy: {version[:50]}"
            server.save()
            
            ServerLog.objects.create(
                server=server,
                action='server_health_check',
                level='success',
                message='Server is healthy',
                details={'version': version}
            )
            
            return True, version
            
        except Exception as e:
            error_msg = str(e)
            
            server.status = 'error'
            server.last_health_check = timezone.now()
            server.health_check_message = f"Error: {error_msg[:200]}"
            server.save()
            
            ServerLog.objects.create(
                server=server,
                action='server_health_check',
                level='error',
                message=f'Health check failed: {error_msg}'
            )
            
            return False, error_msg
    
    def create_database(self, server, db_name, db_username, db_password):
        """
        Create a new database and user on a PostgreSQL server.
        
        Args:
            server: PostgresServer instance
            db_name: Name for the new database
            db_username: Username for database access
            db_password: Password for the database user
            
        Returns:
            bool: Success status
        """
        conn = None
        try:
            # Connect to the server
            conn = self.get_admin_connection(server)
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Create user
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(db_username)
                ),
                [db_password]
            )
            
            # Create database
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(db_name),
                    sql.Identifier(db_username)
                )
            )
            
            # Grant privileges
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(db_name),
                    sql.Identifier(db_username)
                )
            )
            
            cursor.close()
            conn.close()
            
            logger.info(f"Created database {db_name} on {server.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create database: {str(e)}")
            if conn:
                conn.close()
            raise
    
    def drop_database(self, server, db_name, db_username):
        """
        Drop a database and user from a PostgreSQL server.
        
        Args:
            server: PostgresServer instance
            db_name: Name of the database to drop
            db_username: Username to drop
            
        Returns:
            bool: Success status
        """
        conn = None
        try:
            conn = self.get_admin_connection(server)
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Terminate existing connections
            cursor.execute(
                sql.SQL("""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = %s
                    AND pid <> pg_backend_pid()
                """),
                [db_name]
            )
            
            # Drop database
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(db_name)
                )
            )
            
            # Drop user
            cursor.execute(
                sql.SQL("DROP USER IF EXISTS {}").format(
                    sql.Identifier(db_username)
                )
            )
            
            cursor.close()
            conn.close()
            
            logger.info(f"Dropped database {db_name} from {server.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to drop database: {str(e)}")
            if conn:
                conn.close()
            raise
    
    def create_tenant_database(self, server, name=None, display_name=None, created_by=None):
        """
        Create a new tenant database with full setup.
        
        Args:
            server: PostgresServer instance
            name: Database name (auto-generated if not provided)
            display_name: Display name for the database
            created_by: User who created the database
            
        Returns:
            TenantDatabase: The created database instance
        """
        from ..models import TenantDatabase, ServerLog, generate_db_password
        
        if server.is_full:
            raise ValueError(f"Server {server.name} has reached its database limit")
        
        # Create the database record first to get an ID
        tenant_db = TenantDatabase(
            server=server,
            name=name or '',
            display_name=display_name or '',
            db_password=generate_db_password(),
            status='creating',
            created_by=created_by
        )
        
        # Generate name and username if not provided
        if not tenant_db.name:
            tenant_db.name = f"erp_tenant_{str(tenant_db.id).replace('-', '')[:16]}"
        if not tenant_db.db_username:
            tenant_db.db_username = f"user_{str(tenant_db.id).replace('-', '')[:12]}"
        
        tenant_db.save()
        
        try:
            # Create the actual database
            self.create_database(
                server=server,
                db_name=tenant_db.name,
                db_username=tenant_db.db_username,
                db_password=tenant_db.db_password
            )
            
            # Update status
            tenant_db.status = 'active'
            tenant_db.save()
            
            ServerLog.objects.create(
                server=server,
                database=tenant_db,
                action='database_create',
                level='success',
                message=f'Database {tenant_db.name} created successfully',
                user=created_by
            )
            
            # Run migrations
            self.run_migrations(tenant_db)
            
            return tenant_db
            
        except Exception as e:
            tenant_db.status = 'error'
            tenant_db.error_message = str(e)
            tenant_db.save()
            
            ServerLog.objects.create(
                server=server,
                database=tenant_db,
                action='database_create',
                level='error',
                message=f'Failed to create database: {str(e)}',
                user=created_by
            )
            
            raise
    
    def run_migrations(self, tenant_db):
        """
        Run Django migrations on a tenant database.
        
        Args:
            tenant_db: TenantDatabase instance
            
        Returns:
            bool: Success status
        """
        from ..models import ServerLog
        
        # Add the database to Django settings
        db_alias = add_tenant_database(tenant_db)
        
        try:
            out = StringIO()
            
            # Run dependent app migrations first (ERP models have FKs
            # to auth.User / tenants.TenantUser and contenttypes)
            for app in ('contenttypes', 'auth', 'tenants', 'erp'):
                call_command(
                    'migrate',
                    app,
                    database=db_alias,
                    verbosity=1,
                    interactive=False,
                    stdout=out
                )
            
            migration_output = out.getvalue()
            
            # Update migration status
            tenant_db.is_migrated = True
            tenant_db.migrated_at = timezone.now()
            tenant_db.last_migration = migration_output[-200:] if migration_output else 'No output'
            tenant_db.save()
            
            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action='database_migrate',
                level='success',
                message='Migrations completed successfully',
                details={'output': migration_output[:1000]}
            )
            
            logger.info(f"Migrations completed for {tenant_db.name}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            
            tenant_db.error_message = f"Migration error: {error_msg}"
            tenant_db.save()
            
            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action='database_migrate',
                level='error',
                message=f'Migration failed: {error_msg}'
            )
            
            logger.error(f"Migration failed for {tenant_db.name}: {error_msg}")
            raise
    
    def delete_tenant_database(self, tenant_db):
        """
        Delete a tenant database.
        
        Args:
            tenant_db: TenantDatabase instance
            
        Returns:
            bool: Success status
        """
        from ..models import ServerLog
        
        tenant_db.status = 'deleting'
        tenant_db.save()
        
        try:
            self.drop_database(
                server=tenant_db.server,
                db_name=tenant_db.name,
                db_username=tenant_db.db_username
            )
            
            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action='database_delete',
                level='success',
                message=f'Database {tenant_db.name} deleted'
            )
            
            tenant_db.status = 'deleted'
            tenant_db.save()
            
            return True
            
        except Exception as e:
            tenant_db.status = 'error'
            tenant_db.error_message = f"Delete error: {str(e)}"
            tenant_db.save()
            
            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action='database_delete',
                level='error',
                message=f'Failed to delete database: {str(e)}'
            )
            
            raise
    
    def test_database_connection(self, tenant_db):
        """
        Test connection to a tenant database using tenant credentials.
        
        Args:
            tenant_db: TenantDatabase instance
            
        Returns:
            tuple: (success, message)
        """
        try:
            conn = psycopg2.connect(
                host=tenant_db.server.host,
                port=tenant_db.server.port,
                user=tenant_db.db_username,
                password=tenant_db.db_password,
                database=tenant_db.name,
                connect_timeout=10
            )
            conn.close()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)
