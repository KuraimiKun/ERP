"""
Migrate all tenant databases.

Runs Django migrations on all active tenant databases in the correct
dependency order: contenttypes → auth → tenants → erp.

Usage:
    python manage.py migrate_tenants              # migrate all active DBs
    python manage.py migrate_tenants --app erp    # only the erp app
    python manage.py migrate_tenants --database-id <uuid>  # single DB
    python manage.py migrate_tenants --all-apps   # full dependency chain (default)
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database

# The apps that must be migrated on every tenant DB, in dependency order.
TENANT_MIGRATION_ORDER = ('contenttypes', 'auth', 'tenants', 'erp')


class Command(BaseCommand):
    help = 'Run migrations on all active tenant databases'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            default=None,
            help='Only migrate this single app instead of the full chain.',
        )
        parser.add_argument(
            '--database-id',
            type=str,
            default=None,
            help='Specific tenant database UUID to migrate.',
        )
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Also migrate suspended / error databases.',
        )

    def handle(self, *args, **options):
        app_label = options['app']
        database_id = options.get('database_id')
        include_inactive = options.get('include_inactive', False)

        # Determine which apps to migrate
        if app_label:
            apps_to_migrate = (app_label,)
        else:
            apps_to_migrate = TENANT_MIGRATION_ORDER

        # Determine which databases to migrate
        if database_id:
            databases = TenantDatabase.objects.filter(id=database_id)
        elif include_inactive:
            databases = TenantDatabase.objects.exclude(status__in=('creating', 'deleted', 'deleting'))
        else:
            databases = TenantDatabase.objects.filter(status='active')

        total = databases.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No tenant databases found to migrate.'))
            return

        success = 0
        failed = 0

        self.stdout.write(f'Migrating {total} tenant database(s)  '
                          f'apps={", ".join(apps_to_migrate)}\n')

        for tenant_db in databases:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Database: {tenant_db.display_name or tenant_db.name}  '
                              f'(server: {tenant_db.server.name})')

            try:
                db_alias = add_tenant_database(tenant_db)

                for app in apps_to_migrate:
                    self.stdout.write(f'  Migrating {app} …')
                    call_command(
                        'migrate',
                        app,
                        database=db_alias,
                        verbosity=1,
                        interactive=False,
                        stdout=self.stdout,
                    )

                tenant_db.is_migrated = True
                tenant_db.migrated_at = timezone.now()
                tenant_db.error_message = ''
                tenant_db.save(update_fields=['is_migrated', 'migrated_at', 'error_message'])

                self.stdout.write(self.style.SUCCESS(f'  ✓ {tenant_db.name} — all migrations applied'))
                success += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {tenant_db.name} — {e}'))
                tenant_db.error_message = f'Migration error: {e}'
                tenant_db.save(update_fields=['error_message'])
                failed += 1

        self.stdout.write(f'\n{"="*60}')
        self.stdout.write(f'Done — {success} succeeded, {failed} failed out of {total}')
