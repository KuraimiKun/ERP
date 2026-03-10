"""
Initial Setup Command

Creates the initial superuser and optionally sets up a Docker PostgreSQL server.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tenants.models import PostgresServer
from tenants.services.docker_service import DockerService

User = get_user_model()


class Command(BaseCommand):
    help = 'Initial setup for the ERP multi-tenant system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Admin email address',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Admin password',
        )
        parser.add_argument(
            '--create-docker-server',
            action='store_true',
            help='Create a Docker PostgreSQL server',
        )
        parser.add_argument(
            '--docker-port',
            type=int,
            default=5433,
            help='Port for Docker PostgreSQL server (default: 5433)',
        )
        parser.add_argument(
            '--docker-password',
            type=str,
            default='postgres',
            help='Password for Docker PostgreSQL server',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting ERP Multi-Tenant Setup...'))
        
        # Create superuser if it doesn't exist
        email = options.get('email')
        password = options.get('password')
        
        if email and password:
            self.create_superuser(email, password)
        else:
            self.prompt_superuser_creation()
        
        # Create Docker server if requested
        if options.get('create_docker_server'):
            self.create_docker_server(
                port=options['docker_port'],
                password=options['docker_password']
            )
        
        self.stdout.write(self.style.SUCCESS('\nSetup completed successfully!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('  1. Run: python manage.py migrate')
        self.stdout.write('  2. Run: python manage.py runserver')
        self.stdout.write('  3. Visit: http://localhost:8000/admin/')
    
    def create_superuser(self, email, password):
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'User {email} already exists'))
            return
        
        User.objects.create_superuser(
            email=email,
            password=password,
            first_name='Admin',
            last_name='User'
        )
        self.stdout.write(self.style.SUCCESS(f'Created superuser: {email}'))
    
    def prompt_superuser_creation(self):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('Superuser already exists, skipping creation.')
            return
        
        self.stdout.write('\nNo superuser found. Creating one now...')
        
        email = input('Enter admin email: ')
        password = input('Enter admin password: ')
        
        if email and password:
            self.create_superuser(email, password)
        else:
            self.stdout.write(self.style.WARNING('Skipping superuser creation'))
    
    def create_docker_server(self, port, password):
        self.stdout.write('\nCreating Docker PostgreSQL server...')
        
        try:
            docker_service = DockerService()
            
            if not docker_service.is_docker_available():
                self.stdout.write(self.style.ERROR(
                    'Docker is not available. Please install Docker and try again.'
                ))
                return
            
            # Check if server already exists
            if PostgresServer.objects.filter(name='Default Docker Server').exists():
                self.stdout.write(self.style.WARNING(
                    'Default Docker server already exists'
                ))
                return
            
            server = docker_service.create_postgres_container(
                name='Default Docker Server',
                description='Auto-created Docker PostgreSQL server for tenant databases',
                port=port,
                postgres_password=password,
                max_databases=50
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'Created Docker server: {server.name} on port {port}'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create Docker server: {e}'))
