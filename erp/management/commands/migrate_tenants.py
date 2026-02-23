"""
Management command to run ERP migrations on all (or specific) tenant databases.

Usage:
    python manage.py migrate_tenants                    # all active tenants
    python manage.py migrate_tenants --tenant <name>    # specific tenant by db name
"""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database


class Command(BaseCommand):
    help = 'Run ERP migrations on tenant databases.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            default=None,
            help='Tenant database name (e.g. erp_pg_alkuraimi). If omitted, all active tenants are migrated.',
        )
        parser.add_argument(
            '--app',
            type=str,
            default='erp',
            help='App label to migrate (default: erp).',
        )

    def handle(self, *args, **options):
        tenant_name = options['tenant']
        app_label = options['app']

        if tenant_name:
            tenants = TenantDatabase.objects.filter(name=tenant_name, status='active')
            if not tenants.exists():
                self.stderr.write(self.style.ERROR(f"No active tenant database found with name '{tenant_name}'."))
                # Show available tenants
                all_tenants = TenantDatabase.objects.filter(status='active').values_list('name', flat=True)
                if all_tenants:
                    self.stderr.write(f"Available active tenants: {', '.join(all_tenants)}")
                return
        else:
            tenants = TenantDatabase.objects.filter(status='active')

        if not tenants.exists():
            self.stdout.write(self.style.WARNING('No active tenant databases found.'))
            return

        for tenant_db in tenants:
            db_alias = add_tenant_database(tenant_db)
            self.stdout.write(f"\n--- Migrating [{tenant_db.name}] as [{db_alias}] ---")
            try:
                out = StringIO()
                call_command(
                    'migrate',
                    app_label,
                    database=db_alias,
                    verbosity=1,
                    interactive=False,
                    stdout=out,
                )
                output = out.getvalue()
                if output.strip():
                    self.stdout.write(output)
                self.stdout.write(self.style.SUCCESS(f"[{tenant_db.name}] migrated successfully."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[{tenant_db.name}] migration failed: {e}"))
