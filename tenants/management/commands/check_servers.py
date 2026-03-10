"""
Check health of all PostgreSQL servers.

This command performs health checks on all registered PostgreSQL servers.
"""

from django.core.management.base import BaseCommand
from tenants.models import PostgresServer
from tenants.services.database_service import DatabaseService


class Command(BaseCommand):
    help = 'Check health of all PostgreSQL servers'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--server-id',
            type=str,
            help='Specific server ID to check (optional)',
        )
    
    def handle(self, *args, **options):
        server_id = options.get('server_id')
        
        if server_id:
            servers = PostgresServer.objects.filter(id=server_id)
        else:
            servers = PostgresServer.objects.all()
        
        total = servers.count()
        healthy = 0
        unhealthy = 0
        
        self.stdout.write(f'Checking {total} server(s)...\n')
        
        db_service = DatabaseService()
        
        for server in servers:
            self.stdout.write(f'\n{server.name} ({server.host}:{server.port})')
            
            try:
                is_healthy, message = db_service.check_server_health(server)
                
                if is_healthy:
                    self.stdout.write(self.style.SUCCESS('  ✓ Healthy'))
                    self.stdout.write(f'    Databases: {server.database_count}/{server.max_databases}')
                    healthy += 1
                else:
                    self.stdout.write(self.style.WARNING(f'  ⚠ {message}'))
                    unhealthy += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {e}'))
                unhealthy += 1
        
        self.stdout.write(f'\n\nResults: {healthy} healthy, {unhealthy} unhealthy')
