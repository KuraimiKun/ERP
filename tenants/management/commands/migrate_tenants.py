"""
Migrate all tenant databases.

This command runs Django migrations on all active tenant databases.
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database


class Command(BaseCommand):
    help = 'Run migrations on all active tenant databases'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            default='erp',
            help='App to migrate (default: erp)',
        )
        parser.add_argument(
            '--database-id',
            type=str,
            help='Specific database ID to migrate (optional)',
        )
    
    def handle(self, *args, **options):
        app_label = options['app']
        database_id = options.get('database_id')
        
        if database_id:
            # Migrate specific database
            databases = TenantDatabase.objects.filter(id=database_id)
        else:
            # Migrate all active databases
            databases = TenantDatabase.objects.filter(status='active')
        
        total = databases.count()
        success = 0
        failed = 0
        
        self.stdout.write(f'Migrating {total} tenant database(s)...\n')
        
        for tenant_db in databases:
            self.stdout.write(f'\nMigrating: {tenant_db.name}')
            
            try:
                # Add database to settings
                db_alias = add_tenant_database(tenant_db)
                
                # Run migrations
                call_command(
                    'migrate',
                    app_label,
                    database=db_alias,
                    verbosity=1,
                    interactive=False,
                )
                
                # Update status
                tenant_db.is_migrated = True
                tenant_db.save()
                
                self.stdout.write(self.style.SUCCESS(f'  ✓ Success'))
                success += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Failed: {e}'))
                failed += 1
        
        self.stdout.write(f'\nCompleted: {success} successful, {failed} failed')
