"""
Database Service

Handles database creation, migration, and management for tenant databases.
Enterprise features: size monitoring, active connections, table stats,
cloning, export/import, maintenance (VACUUM/ANALYZE/REINDEX),
performance analytics, password reset, and connection management.
"""

import logging
import os
import secrets
import stat
import string
import subprocess
import tempfile
import uuid
import psycopg2
from psycopg2 import sql
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from io import StringIO

from ..routers import add_tenant_database

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
        company_name=getattr(user, "company_name", ""),
        phone=getattr(user, "phone", ""),
        password=user.password,  # hashed – not used for login here
        is_active=user.is_active,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
        is_approved=getattr(user, "is_approved", True),
        approval_status=getattr(user, "approval_status", "approved"),
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

    # ── .pgpass helpers ──────────────────────────────────────────────────

    @staticmethod
    def _write_pgpass(host, port, database, user, password):
        """Create a temporary .pgpass file with 0600 permissions.

        Returns the path to the file.  The caller MUST clean it up
        via ``_cleanup_pgpass`` (use a ``finally`` block).
        """

        # Escape colons and backslashes per pgpass format
        def _esc(v):
            return str(v).replace("\\", "\\\\").replace(":", "\\:")

        line = f"{_esc(host)}:{_esc(port)}:{_esc(database)}:{_esc(user)}:{_esc(password)}\n"

        fd, path = tempfile.mkstemp(prefix=".pgpass_", suffix=".tmp")
        try:
            os.write(fd, line.encode())
        finally:
            os.close(fd)

        # Restrict to owner-only on platforms that support it
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except OSError:
            pass  # Windows — permissions handled by user account

        return path

    @staticmethod
    def _cleanup_pgpass(path):
        try:
            os.remove(path)
        except OSError:
            pass

    # ── connections ──────────────────────────────────────────────────────

    def get_admin_connection(self, server, database="postgres"):
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
            connect_timeout=10,
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
            server.status = "active"
            server.last_health_check = timezone.now()
            server.health_check_message = f"Healthy: {version[:50]}"
            server.save()

            ServerLog.objects.create(
                server=server,
                action="server_health_check",
                level="success",
                message="Server is healthy",
                details={"version": version},
            )

            return True, version

        except Exception as e:
            error_msg = str(e)

            server.status = "error"
            server.last_health_check = timezone.now()
            server.health_check_message = f"Error: {error_msg[:200]}"
            server.save()

            ServerLog.objects.create(
                server=server, action="server_health_check", level="error", message=f"Health check failed: {error_msg}"
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
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(sql.Identifier(db_username)), [db_password]
            )

            # Create database
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(db_name), sql.Identifier(db_username))
            )

            # Grant privileges
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(db_name), sql.Identifier(db_username)
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
                [db_name],
            )

            # Drop database
            cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))

            # Drop user
            cursor.execute(sql.SQL("DROP USER IF EXISTS {}").format(sql.Identifier(db_username)))

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
            name=name or "",
            display_name=display_name or "",
            db_password=generate_db_password(),
            status="creating",
            created_by=created_by,
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
                db_password=tenant_db.db_password,
            )

            # Update status
            tenant_db.status = "active"
            tenant_db.save()

            ServerLog.objects.create(
                server=server,
                database=tenant_db,
                action="database_create",
                level="success",
                message=f"Database {tenant_db.name} created successfully",
                user=created_by,
            )

            # Run migrations
            self.run_migrations(tenant_db)

            return tenant_db

        except Exception as e:
            tenant_db.status = "error"
            tenant_db.error_message = str(e)
            tenant_db.save()

            ServerLog.objects.create(
                server=server,
                database=tenant_db,
                action="database_create",
                level="error",
                message=f"Failed to create database: {str(e)}",
                user=created_by,
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
            for app in ("contenttypes", "auth", "authtoken", "tenants", "erp", "erp_ai"):
                call_command("migrate", app, database=db_alias, verbosity=1, interactive=False, stdout=out)

            migration_output = out.getvalue()

            # Update migration status
            tenant_db.is_migrated = True
            tenant_db.migrated_at = timezone.now()
            tenant_db.last_migration = migration_output[-200:] if migration_output else "No output"
            tenant_db.save()

            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action="database_migrate",
                level="success",
                message="Migrations completed successfully",
                details={"output": migration_output[:1000]},
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
                action="database_migrate",
                level="error",
                message=f"Migration failed: {error_msg}",
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

        tenant_db.status = "deleting"
        tenant_db.save()

        try:
            self.drop_database(server=tenant_db.server, db_name=tenant_db.name, db_username=tenant_db.db_username)

            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action="database_delete",
                level="success",
                message=f"Database {tenant_db.name} deleted",
            )

            tenant_db.status = "deleted"
            tenant_db.save()

            return True

        except Exception as e:
            tenant_db.status = "error"
            tenant_db.error_message = f"Delete error: {str(e)}"
            tenant_db.save()

            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action="database_delete",
                level="error",
                message=f"Failed to delete database: {str(e)}",
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
                connect_timeout=10,
            )
            conn.close()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)

    # ── Enterprise Features ───────────────────────────────────────────────

    def get_database_size(self, tenant_db):
        """
        Get the size of a tenant database in a human-readable format.

        Returns dict with raw_bytes and pretty (e.g. '15 MB').
        """
        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_database_size(%s), pg_size_pretty(pg_database_size(%s))",
                    [tenant_db.name, tenant_db.name],
                )
                row = cur.fetchone()
                return {"raw_bytes": row[0], "pretty": row[1]}
        except Exception as e:
            logger.error(f"Error getting database size for {tenant_db.name}: {e}")
            return {"raw_bytes": 0, "pretty": "N/A"}
        finally:
            if conn:
                conn.close()

    def get_active_connections(self, tenant_db):
        """
        List active connections to a tenant database.

        Returns list of dicts with pid, user, state, query, client_addr,
        backend_start, query_start, wait_event, wait_event_type.
        """
        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pid, usename, state, query,
                           client_addr::text, backend_start::text,
                           query_start::text, wait_event_type, wait_event,
                           state_change::text
                    FROM pg_stat_activity
                    WHERE datname = %s
                    ORDER BY backend_start DESC
                """,
                    [tenant_db.name],
                )
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting active connections for {tenant_db.name}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def terminate_connection(self, tenant_db, pid):
        """Terminate a specific backend connection by PID."""
        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server)
            with conn.cursor() as cur:
                cur.execute("SELECT pg_terminate_backend(%s)", [pid])
                return True
        except Exception as e:
            logger.error(f"Error terminating PID {pid}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def terminate_all_connections(self, tenant_db):
        """Terminate all connections to a tenant database (except our own)."""
        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                    [tenant_db.name],
                )
                terminated = cur.rowcount
                return terminated
        except Exception as e:
            logger.error(f"Error terminating connections for {tenant_db.name}: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    def get_table_stats(self, tenant_db):
        """
        Get table-level statistics for a tenant database: row counts,
        sizes, index sizes, dead tuples.

        Connects as tenant user to the tenant database.
        """
        conn = None
        try:
            conn = psycopg2.connect(
                host=tenant_db.server.host,
                port=tenant_db.server.port,
                user=tenant_db.db_username,
                password=tenant_db.db_password,
                database=tenant_db.name,
                connect_timeout=10,
            )
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        schemaname,
                        relname AS table_name,
                        n_live_tup AS live_rows,
                        n_dead_tup AS dead_rows,
                        pg_size_pretty(pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(relname))) AS total_size,
                        pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(relname)) AS total_size_bytes,
                        pg_size_pretty(pg_relation_size(quote_ident(schemaname)||'.'||quote_ident(relname))) AS table_size,
                        pg_size_pretty(pg_indexes_size(quote_ident(schemaname)||'.'||quote_ident(relname)::regclass)) AS index_size,
                        last_vacuum::text,
                        last_analyze::text,
                        last_autovacuum::text,
                        last_autoanalyze::text
                    FROM pg_stat_user_tables
                    ORDER BY pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(relname)) DESC
                """)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting table stats for {tenant_db.name}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_database_performance(self, tenant_db):
        """
        Get performance metrics: cache hit ratio, index usage ratio,
        transaction stats, dead tuple ratio, conflicts, deadlocks.
        """
        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server)
            result = {}

            with conn.cursor() as cur:
                # Cache hit ratio
                cur.execute(
                    """
                    SELECT
                        COALESCE(sum(blks_hit), 0) AS hits,
                        COALESCE(sum(blks_read), 0) AS reads,
                        CASE WHEN sum(blks_hit) + sum(blks_read) > 0
                             THEN round(100.0 * sum(blks_hit) / (sum(blks_hit) + sum(blks_read)), 2)
                             ELSE 0 END AS cache_hit_ratio
                    FROM pg_stat_database WHERE datname = %s
                """,
                    [tenant_db.name],
                )
                row = cur.fetchone()
                result["cache_hits"] = row[0]
                result["cache_reads"] = row[1]
                result["cache_hit_ratio"] = float(row[2])

                # Transaction stats
                cur.execute(
                    """
                    SELECT xact_commit, xact_rollback, tup_returned, tup_fetched,
                           tup_inserted, tup_updated, tup_deleted, conflicts, deadlocks,
                           temp_files, temp_bytes, blk_read_time, blk_write_time
                    FROM pg_stat_database WHERE datname = %s
                """,
                    [tenant_db.name],
                )
                row = cur.fetchone()
                if row:
                    result.update(
                        {
                            "xact_commit": row[0] or 0,
                            "xact_rollback": row[1] or 0,
                            "tup_returned": row[2] or 0,
                            "tup_fetched": row[3] or 0,
                            "tup_inserted": row[4] or 0,
                            "tup_updated": row[5] or 0,
                            "tup_deleted": row[6] or 0,
                            "conflicts": row[7] or 0,
                            "deadlocks": row[8] or 0,
                            "temp_files": row[9] or 0,
                            "temp_bytes": row[10] or 0,
                            "blk_read_time_ms": float(row[11] or 0),
                            "blk_write_time_ms": float(row[12] or 0),
                        }
                    )

                # Index usage ratio
                cur.execute("""
                    SELECT
                        COALESCE(sum(idx_scan), 0) AS idx_scans,
                        COALESCE(sum(seq_scan), 0) AS seq_scans,
                        CASE WHEN sum(idx_scan) + sum(seq_scan) > 0
                             THEN round(100.0 * sum(idx_scan) / (sum(idx_scan) + sum(seq_scan)), 2)
                             ELSE 0 END AS index_usage_ratio
                    FROM pg_stat_user_tables
                """)
                row = cur.fetchone()
                result["index_scans"] = row[0]
                result["sequential_scans"] = row[1]
                result["index_usage_ratio"] = float(row[2])

                # Total dead tuples
                cur.execute("""
                    SELECT COALESCE(sum(n_dead_tup), 0) FROM pg_stat_user_tables
                """)
                result["total_dead_tuples"] = cur.fetchone()[0]

            return result
        except Exception as e:
            logger.error(f"Error getting performance stats for {tenant_db.name}: {e}")
            return {}
        finally:
            if conn:
                conn.close()

    def get_long_running_queries(self, tenant_db, min_seconds=5):
        """
        Get queries running longer than min_seconds.
        """
        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pid, usename, state, query, client_addr::text,
                           now() - query_start AS duration,
                           extract(epoch FROM now() - query_start)::int AS duration_secs,
                           wait_event_type, wait_event
                    FROM pg_stat_activity
                    WHERE datname = %s
                      AND state = 'active'
                      AND query NOT ILIKE '%%pg_stat_activity%%'
                      AND now() - query_start > interval '%s seconds'
                    ORDER BY duration DESC
                """,
                    [tenant_db.name, min_seconds],
                )
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting long running queries for {tenant_db.name}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def run_maintenance(self, tenant_db, operation="vacuum"):
        """
        Run maintenance operation on a tenant database.
        operation: 'vacuum', 'vacuum_full', 'analyze', 'vacuum_analyze', 'reindex'

        Returns (success, message).
        """
        from ..models import ServerLog

        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server, database=tenant_db.name)
            conn.autocommit = True

            with conn.cursor() as cur:
                if operation == "vacuum":
                    cur.execute("VACUUM")
                elif operation == "vacuum_full":
                    cur.execute("VACUUM FULL")
                elif operation == "analyze":
                    cur.execute("ANALYZE")
                elif operation == "vacuum_analyze":
                    cur.execute("VACUUM ANALYZE")
                elif operation == "reindex":
                    cur.execute(sql.SQL("REINDEX DATABASE {}").format(sql.Identifier(tenant_db.name)))
                else:
                    return False, f"Unknown operation: {operation}"

            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action="database_maintenance",
                level="success",
                message=f"Maintenance ({operation}) completed on {tenant_db.name}",
                details={"operation": operation},
            )

            return True, f"{operation.upper()} completed successfully"
        except Exception as e:
            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action="database_maintenance",
                level="error",
                message=f"Maintenance ({operation}) failed: {str(e)}",
                details={"operation": operation},
            )
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def export_database(self, tenant_db):
        """
        Export (pg_dump) a tenant database to a SQL file.
        Backups are stored outside the web-accessible media directory.
        Returns (success, file_path_or_error).
        """
        from ..models import ServerLog

        backup_dir = os.path.join(settings.BASE_DIR, "private_backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{tenant_db.name}_{timestamp}_{uuid.uuid4().hex[:8]}.sql"
        filepath = os.path.join(backup_dir, filename)

        env = os.environ.copy()

        cmd = [
            "pg_dump",
            "-h",
            tenant_db.server.host,
            "-p",
            str(tenant_db.server.port),
            "-U",
            tenant_db.server.admin_username,
            "-d",
            tenant_db.name,
            "-F",
            "p",  # plain SQL format
            "-f",
            filepath,
        ]

        pgpass_path = None
        try:
            pgpass_path = self._write_pgpass(
                tenant_db.server.host,
                str(tenant_db.server.port),
                tenant_db.name,
                tenant_db.server.admin_username,
                tenant_db.server.admin_password,
            )
            env["PGPASSFILE"] = pgpass_path

            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                file_size = os.path.getsize(filepath)
                ServerLog.objects.create(
                    server=tenant_db.server,
                    database=tenant_db,
                    action="database_backup",
                    level="success",
                    message=f"Database exported: {filename} ({file_size} bytes)",
                    details={"filename": filename, "size": file_size},
                )
                return True, filepath
            else:
                error = result.stderr
                ServerLog.objects.create(
                    server=tenant_db.server,
                    database=tenant_db,
                    action="database_backup",
                    level="error",
                    message=f"Export failed: {error}",
                )
                return False, error
        except FileNotFoundError:
            msg = "pg_dump not found. Ensure PostgreSQL client tools are installed."
            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action="database_backup",
                level="error",
                message=msg,
            )
            return False, msg
        except subprocess.TimeoutExpired:
            return False, "Export timed out after 600 seconds"
        except Exception as e:
            return False, str(e)
        finally:
            if pgpass_path:
                self._cleanup_pgpass(pgpass_path)

    def import_database(self, tenant_db, sql_file_path):
        """
        Import (psql) a SQL file into a tenant database.
        Returns (success, message).
        """
        from ..models import ServerLog

        if not os.path.exists(sql_file_path):
            return False, "SQL file not found"

        env = os.environ.copy()

        cmd = [
            "psql",
            "-h",
            tenant_db.server.host,
            "-p",
            str(tenant_db.server.port),
            "-U",
            tenant_db.server.admin_username,
            "-d",
            tenant_db.name,
            "-f",
            sql_file_path,
        ]

        pgpass_path = None
        try:
            pgpass_path = self._write_pgpass(
                tenant_db.server.host,
                str(tenant_db.server.port),
                tenant_db.name,
                tenant_db.server.admin_username,
                tenant_db.server.admin_password,
            )
            env["PGPASSFILE"] = pgpass_path

            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                ServerLog.objects.create(
                    server=tenant_db.server,
                    database=tenant_db,
                    action="database_restore",
                    level="success",
                    message=f"Database imported from {os.path.basename(sql_file_path)}",
                )
                return True, "Import completed successfully"
            else:
                error = result.stderr
                ServerLog.objects.create(
                    server=tenant_db.server,
                    database=tenant_db,
                    action="database_restore",
                    level="error",
                    message=f"Import failed: {error}",
                )
                return False, error
        except FileNotFoundError:
            return False, "psql not found. Ensure PostgreSQL client tools are installed."
        except subprocess.TimeoutExpired:
            return False, "Import timed out after 600 seconds"
        except Exception as e:
            return False, str(e)
        finally:
            if pgpass_path:
                self._cleanup_pgpass(pgpass_path)

    def clone_database(self, source_db, new_name, new_display_name, created_by):
        """
        Clone a tenant database by doing pg_dump → create new DB → psql import.
        Returns (success, new_tenant_db_or_error).
        """
        from ..models import ServerLog

        # Step 1: Export the source
        success, filepath = self.export_database(source_db)
        if not success:
            return False, f"Export failed: {filepath}"

        # Step 2: Create a new database
        try:
            new_db = self.create_tenant_database(
                server=source_db.server,
                name=new_name,
                display_name=new_display_name,
                created_by=created_by,
            )
        except Exception as e:
            # Clean up export file
            if os.path.exists(filepath):
                os.remove(filepath)
            return False, f"Create failed: {str(e)}"

        # Step 3: Import into new database
        success, msg = self.import_database(new_db, filepath)

        # Clean up export file
        if os.path.exists(filepath):
            os.remove(filepath)

        if success:
            ServerLog.objects.create(
                server=source_db.server,
                database=new_db,
                action="database_clone",
                level="success",
                message=f"Cloned from {source_db.name} to {new_db.name}",
                details={"source": source_db.name},
            )
            return True, new_db
        else:
            return False, f"Import failed: {msg}"

    def reset_database_password(self, tenant_db):
        """
        Generate a new password for the tenant database user
        and update it in both PostgreSQL and TenantDatabase model.

        Returns (success, message).
        """
        from ..models import ServerLog

        new_password = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))

        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("ALTER USER {} WITH PASSWORD %s").format(sql.Identifier(tenant_db.db_username)),
                    [new_password],
                )

            tenant_db.db_password = new_password
            tenant_db.save()

            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action="database_update",
                level="success",
                message=f"Password reset for user {tenant_db.db_username}",
            )

            return True, "Password reset successful"
        except Exception as e:
            ServerLog.objects.create(
                server=tenant_db.server,
                database=tenant_db,
                action="database_update",
                level="error",
                message=f"Password reset failed: {str(e)}",
            )
            return False, str(e)
        finally:
            if conn:
                conn.close()

    def get_database_locks(self, tenant_db):
        """Get current lock information for a database."""
        conn = None
        try:
            conn = self.get_admin_connection(tenant_db.server)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        l.pid,
                        a.usename,
                        l.locktype,
                        l.mode,
                        l.granted,
                        a.query,
                        a.state,
                        l.relation::regclass::text AS relation
                    FROM pg_locks l
                    JOIN pg_stat_activity a ON l.pid = a.pid
                    WHERE a.datname = %s
                    ORDER BY l.granted, l.pid
                """,
                    [tenant_db.name],
                )
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting locks for {tenant_db.name}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_index_stats(self, tenant_db):
        """
        Get index usage statistics for a database.
        Shows unused, rarely-used, or bloated indexes.
        """
        conn = None
        try:
            conn = psycopg2.connect(
                host=tenant_db.server.host,
                port=tenant_db.server.port,
                user=tenant_db.db_username,
                password=tenant_db.db_password,
                database=tenant_db.name,
                connect_timeout=10,
            )
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        schemaname,
                        relname AS table_name,
                        indexrelname AS index_name,
                        idx_scan AS scans,
                        idx_tup_read AS tuples_read,
                        idx_tup_fetch AS tuples_fetched,
                        pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
                        pg_relation_size(indexrelid) AS index_size_bytes
                    FROM pg_stat_user_indexes
                    ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
                """)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting index stats for {tenant_db.name}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_server_databases_overview(self, server):
        """
        Get overview of ALL databases on a server with their sizes.
        """
        conn = None
        try:
            conn = self.get_admin_connection(server)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size,
                           pg_database_size(datname) AS size_bytes,
                           (SELECT count(*) FROM pg_stat_activity WHERE datname = d.datname) AS connections
                    FROM pg_database d
                    WHERE NOT datistemplate
                    ORDER BY pg_database_size(datname) DESC
                """)
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting server databases overview: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_server_settings(self, server):
        """Get key PostgreSQL configuration settings."""
        conn = None
        try:
            conn = self.get_admin_connection(server)
            important_settings = [
                "max_connections",
                "shared_buffers",
                "effective_cache_size",
                "work_mem",
                "maintenance_work_mem",
                "wal_buffers",
                "checkpoint_completion_target",
                "random_page_cost",
                "effective_io_concurrency",
                "max_worker_processes",
                "max_parallel_workers",
                "max_wal_size",
                "min_wal_size",
                "log_min_duration_statement",
                "timezone",
                "server_version",
            ]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT name, setting, unit, short_desc, category
                    FROM pg_settings
                    WHERE name = ANY(%s)
                    ORDER BY category, name
                """,
                    [important_settings],
                )
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting server settings: {e}")
            return []
        finally:
            if conn:
                conn.close()
