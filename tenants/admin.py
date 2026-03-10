"""
Admin Configuration for Tenant Management

Provides comprehensive admin interface for managing:
- Users and their approval workflow
- PostgreSQL servers (remote and Docker)
- Tenant databases
- Database assignments
"""

import logging
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django import forms as forms

from .models import (
    TenantUser, PostgresServer, TenantDatabase,
    DatabaseAssignment, ServerLog
)
from .platform_admin.forms import UserApprovalForm, UserRejectionForm, DockerServerForm, UserAssignExistingDatabaseForm
from .services.database_service import DatabaseService
from .services.docker_service import DockerService

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Admin Site
# =============================================================================

class TenantAdminSite(admin.AdminSite):
    """Custom admin site for tenant management."""
    site_header = 'ERP Multi-Tenant Administration'
    site_title = 'ERP Admin'
    index_title = 'Tenant Management'


# =============================================================================
# User Admin
# =============================================================================

@admin.register(TenantUser)
class TenantUserAdmin(UserAdmin):
    """Admin interface for TenantUser model."""
    
    list_display = [
        'email', 'get_full_name', 'company_name', 'approval_status_badge',
        'assigned_database_link', 'is_staff', 'created_at'
    ]
    list_filter = ['approval_status', 'is_staff', 'is_superuser', 'is_active', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'company_name']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'company_name', 'phone')}),
        ('Approval Status', {
            'fields': ('approval_status', 'is_approved', 'approved_by', 'approved_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'approved_by', 'approved_at', 'date_joined', 'last_login']
    
    actions = ['approve_users', 'reject_users', 'suspend_users']
    
    def approval_status_badge(self, obj):
        """Display approval status as a colored badge."""
        colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'suspended': 'secondary',
        }
        color = colors.get(obj.approval_status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_approval_status_display()
        )
    approval_status_badge.short_description = 'Status'
    approval_status_badge.admin_order_field = 'approval_status'
    
    def assigned_database_link(self, obj):
        """Display assigned database as a link."""
        db = obj.assigned_database
        if db:
            url = reverse('admin:tenants_tenantdatabase_change', args=[db.pk])
            return format_html('<a href="{}">{}</a>', url, db.display_name or db.name)
        return format_html('<span class="text-muted">Not assigned</span>')
    assigned_database_link.short_description = 'Database'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:user_id>/approve/',
                self.admin_site.admin_view(self.approve_user_view),
                name='tenants_tenantuser_approve'
            ),
            path(
                '<int:user_id>/reject/',
                self.admin_site.admin_view(self.reject_user_view),
                name='tenants_tenantuser_reject'
            ),
            path(
                '<int:user_id>/assign-database/',
                self.admin_site.admin_view(self.assign_database_view),
                name='tenants_tenantuser_assign_database'
            ),
        ]
        return custom_urls + urls
    
    def approve_user_view(self, request, user_id):
        """View for approving a user and creating their database."""
        user = get_object_or_404(TenantUser, pk=user_id)
        
        if user.is_approved:
            messages.warning(request, f'User {user.email} is already approved.')
            return redirect('admin:tenants_tenantuser_changelist')
        
        if request.method == 'POST':
            form = UserApprovalForm(request.POST)
            if form.is_valid():
                server = form.cleaned_data['server']
                database_name = form.cleaned_data['database_name']
                display_name = form.cleaned_data['display_name'] or f"{user.company_name or user.email}'s Database"
                
                try:
                    # Create database
                    db_service = DatabaseService()
                    tenant_db = db_service.create_tenant_database(
                        server=server,
                        name=database_name,
                        display_name=display_name,
                        created_by=request.user
                    )
                    
                    # Approve user
                    user.approve(request.user)
                    
                    # Assign database to user
                    DatabaseAssignment.objects.create(
                        user=user,
                        database=tenant_db,
                        role='owner',
                        assigned_by=request.user
                    )
                    
                    messages.success(
                        request,
                        f'User {user.email} has been approved and assigned to database {tenant_db.name}'
                    )
                    return redirect('admin:tenants_tenantuser_changelist')
                    
                except Exception as e:
                    messages.error(request, f'Error creating database: {str(e)}')
        else:
            form = UserApprovalForm()
        
        context = {
            **self.admin_site.each_context(request),
            'user': user,
            'form': form,
            'title': f'Approve User: {user.email}',
            'opts': self.model._meta,
        }
        return render(request, 'admin/tenants/tenantuser/approve.html', context)
    
    def reject_user_view(self, request, user_id):
        """View for rejecting a user application."""
        user = get_object_or_404(TenantUser, pk=user_id)
        
        if request.method == 'POST':
            form = UserRejectionForm(request.POST)
            if form.is_valid():
                user.reject(form.cleaned_data['reason'])
                messages.success(request, f'User {user.email} has been rejected.')
                return redirect('admin:tenants_tenantuser_changelist')
        else:
            form = UserRejectionForm()
        
        context = {
            **self.admin_site.each_context(request),
            'user': user,
            'form': form,
            'title': f'Reject User: {user.email}',
            'opts': self.model._meta,
        }
        return render(request, 'admin/tenants/tenantuser/reject.html', context)
    
    def assign_database_view(self, request, user_id):
        """View for assigning an existing database to a user."""
        user = get_object_or_404(TenantUser, pk=user_id)
        
        if request.method == 'POST':
            form = UserAssignExistingDatabaseForm(request.POST)
            if form.is_valid():
                database = form.cleaned_data['database']
                role = form.cleaned_data['role']
                
                # Deactivate existing assignments
                user.database_assignments.filter(is_active=True).update(
                    is_active=False,
                    deactivated_at=timezone.now()
                )
                
                # Create new assignment
                DatabaseAssignment.objects.create(
                    user=user,
                    database=database,
                    role=role,
                    assigned_by=request.user
                )
                
                # Ensure user is approved
                if not user.is_approved:
                    user.approve(request.user)
                
                messages.success(
                    request,
                    f'User {user.email} has been assigned to database {database.name}'
                )
                return redirect('admin:tenants_tenantuser_changelist')
        else:
            form = UserAssignExistingDatabaseForm()
        
        context = {
            **self.admin_site.each_context(request),
            'user': user,
            'form': form,
            'title': f'Assign Database to: {user.email}',
            'opts': self.model._meta,
        }
        return render(request, 'admin/tenants/tenantuser/assign_database.html', context)
    
    @admin.action(description='Approve selected users')
    def approve_users(self, request, queryset):
        """Bulk approve users (without database assignment)."""
        for user in queryset.filter(approval_status='pending'):
            user.approve(request.user)
        messages.success(request, 'Users approved. Remember to assign databases.')
    
    @admin.action(description='Reject selected users')
    def reject_users(self, request, queryset):
        """Bulk reject users."""
        queryset.filter(approval_status='pending').update(
            approval_status='rejected',
            is_approved=False
        )
        messages.success(request, 'Selected users have been rejected.')
    
    @admin.action(description='Suspend selected users')
    def suspend_users(self, request, queryset):
        """Bulk suspend users."""
        queryset.update(
            approval_status='suspended',
            is_approved=False,
            is_active=False
        )
        messages.success(request, 'Selected users have been suspended.')


# =============================================================================
# PostgreSQL Server Admin
# =============================================================================

class PostgresServerAdminForm(forms.ModelForm):
    """
    Custom form for PostgresServer that provides smart defaults for Docker servers
    and auto-creates the Docker container on save.
    """

    class Meta:
        model = PostgresServer
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # When adding a new server, provide smart Docker defaults
        if not self.instance.pk:
            # Auto-generate a secure password
            import secrets
            import string
            auto_pass = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))
            self.fields['admin_password'].initial = auto_pass

            # Pick the next available port (5432, 5433, 5434, …)
            used_ports = set(
                PostgresServer.objects.values_list('port', flat=True)
            )
            next_port = 5432
            while next_port in used_ports:
                next_port += 1
            self.fields['port'].initial = next_port
            self.fields['host'].initial = 'localhost'
            self.fields['admin_username'].initial = 'postgres'
            self.fields['max_databases'].initial = 50

            # Make Docker-only fields optional so the form validates
            # before we fill them in programmatically
            for f in ('docker_container_id', 'docker_container_name', 'docker_volume_name'):
                if f in self.fields:
                    self.fields[f].required = False

        # Show the password value (Django hides it by default for PasswordInput)
        self.fields['admin_password'].widget = forms.TextInput(
            attrs={'class': 'vTextField', 'style': 'font-family: monospace;'}
        )

    def clean(self):
        cleaned = super().clean()
        stype = cleaned.get('server_type')

        if stype == 'remote':
            # Remote servers need host info filled in by the admin
            if not cleaned.get('host'):
                self.add_error('host', 'Host is required for remote servers.')
            if not cleaned.get('admin_password'):
                self.add_error('admin_password', 'Password is required for remote servers.')

        return cleaned


@admin.register(PostgresServer)
class PostgresServerAdmin(admin.ModelAdmin):
    """
    Admin interface for PostgreSQL servers.

    When adding a new server with server_type='docker', the Docker container is
    created automatically with recommended settings.  The admin only needs to
    provide a *name* (and optionally tweak port / password / capacity).
    """

    form = PostgresServerAdminForm

    list_display = [
        'name', 'server_type_badge', 'host_port', 'status_badge',
        'database_capacity', 'last_health_check'
    ]
    list_filter = ['server_type', 'status', 'created_at']
    search_fields = ['name', 'host', 'description']
    readonly_fields = [
        'id', 'docker_container_id', 'docker_container_name', 'docker_volume_name',
        'last_health_check', 'health_check_message', 'created_at', 'updated_at', 'created_by'
    ]

    # ---- fieldsets for *editing* an existing server --------------------------
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'server_type', 'status')
        }),
        ('Connection', {
            'fields': ('host', 'port', 'admin_username', 'admin_password')
        }),
        ('Capacity', {
            'fields': ('max_databases',)
        }),
        ('Docker Information', {
            'fields': ('docker_container_id', 'docker_container_name', 'docker_volume_name'),
            'classes': ('collapse',)
        }),
        ('Health & Monitoring', {
            'fields': ('last_health_check', 'health_check_message'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    # ---- simplified fieldsets for *adding* a new server ----------------------
    add_fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'server_type'),
            'description': (
                'Choose <strong>Docker</strong> to spin up a local PostgreSQL '
                'container automatically, or <strong>Remote</strong> to '
                'register an existing server.'
            ),
        }),
        ('Connection', {
            'fields': ('host', 'port', 'admin_username', 'admin_password'),
            'description': (
                'For Docker servers these are pre-filled with recommended '
                'defaults. You may adjust the port or password if needed.'
            ),
        }),
        ('Capacity', {
            'fields': ('max_databases',)
        }),
    )

    actions = ['check_server_health', 'start_docker_containers', 'stop_docker_containers']

    # ---- Use add_fieldsets on the create page --------------------------------
    def get_fieldsets(self, request, obj=None):
        if obj is None:  # Adding
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj is None:  # Adding – nothing is readonly
            return []
        return self.readonly_fields

    # ---- Auto-create Docker container on save --------------------------------
    def save_model(self, request, obj, form, change):
        """
        When creating a new Docker server, automatically create the container,
        then populate the Docker fields and run a health check.
        """
        if not change and obj.server_type == 'docker':
            # ---- Docker auto-creation path ----
            docker_svc = DockerService()

            if not docker_svc.is_docker_available():
                messages.error(
                    request,
                    'Docker is not available or not running on this machine. '
                    'Please install / start Docker and try again.'
                )
                return  # Don't save – let the admin retry

            # Ensure the Docker network exists
            docker_svc.ensure_network_exists()

            # Build container name from the server name
            import re
            safe_name = re.sub(r'[^a-z0-9_-]', '_', obj.name.lower()).strip('_')
            container_name = f"erp_pg_{safe_name}"
            volume_name = f"{container_name}_data"

            # Create the container
            cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--network", docker_svc.network_name,
                "-e", f"POSTGRES_PASSWORD={obj.admin_password}",
                "-p", f"{obj.port}:5432",
                "-v", f"{volume_name}:/var/lib/postgresql/data",
                "--restart", "unless-stopped",
                docker_svc.postgres_image,
            ]
            success, output = docker_svc._run_command(cmd, check=False)

            if not success:
                messages.error(
                    request,
                    f'Failed to create Docker container: {output}'
                )
                return  # Don't save

            # Populate Docker-specific fields
            obj.docker_container_id = output[:12]
            obj.docker_container_name = container_name
            obj.docker_volume_name = volume_name
            obj.host = 'localhost'
            obj.admin_username = obj.admin_username or 'postgres'
            obj.status = 'inactive'  # Will flip to active after health check
            obj.created_by = request.user

            # Save to DB first so the health check / logs can reference it
            super().save_model(request, obj, form, change)

            # Log the creation
            ServerLog.objects.create(
                server=obj,
                action='docker_container_create',
                level='success',
                message=f'Docker container {container_name} created automatically',
                user=request.user,
                details={
                    'container_id': obj.docker_container_id,
                    'port': obj.port,
                    'image': docker_svc.postgres_image,
                }
            )

            # Wait for PostgreSQL to be ready, then health-check
            import time
            time.sleep(5)
            db_svc = DatabaseService()
            for _ in range(10):
                is_healthy, msg = db_svc.check_server_health(obj)
                if is_healthy:
                    messages.success(
                        request,
                        f'Docker PostgreSQL server "{obj.name}" created and '
                        f'healthy on port {obj.port}.'
                    )
                    return  # Already saved
                time.sleep(2)

            # If we get here the server started but isn't healthy yet
            messages.warning(
                request,
                'Docker container created but PostgreSQL is not responding yet. '
                'Check the server health in a moment.'
            )
            return  # Already saved

        # ---- Remote server or editing an existing server ----
        obj.created_by = obj.created_by or request.user
        super().save_model(request, obj, form, change)

    # ---- response_add: skip the "continue editing" redirect ------------------
    def response_add(self, request, obj, post_url_continue=None):
        """After adding, go straight to the changelist."""
        if "_continue" not in request.POST and "_addanother" not in request.POST:
            messages.info(request, f'Server "{obj.name}" saved.')
            return redirect('admin:tenants_postgresserver_changelist')
        return super().response_add(request, obj, post_url_continue)

    # ---- Inject JS/CSS for the add page to toggle Docker vs Remote fields ----
    class Media:
        js = ('admin/js/server_type_toggle.js',)
    
    def server_type_badge(self, obj):
        color = 'primary' if obj.server_type == 'docker' else 'info'
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_server_type_display()
        )
    server_type_badge.short_description = 'Type'
    
    def host_port(self, obj):
        return f"{obj.host}:{obj.port}"
    host_port.short_description = 'Host:Port'
    
    def status_badge(self, obj):
        colors = {
            'active': 'success',
            'inactive': 'secondary',
            'maintenance': 'warning',
            'error': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def database_capacity(self, obj):
        return f"{obj.database_count} / {obj.max_databases}"
    database_capacity.short_description = 'Databases'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'create-docker/',
                self.admin_site.admin_view(self.create_docker_server_view),
                name='tenants_postgresserver_create_docker'
            ),
            path(
                '<uuid:server_id>/start/',
                self.admin_site.admin_view(self.start_server_view),
                name='tenants_postgresserver_start'
            ),
            path(
                '<uuid:server_id>/stop/',
                self.admin_site.admin_view(self.stop_server_view),
                name='tenants_postgresserver_stop'
            ),
            path(
                '<uuid:server_id>/health-check/',
                self.admin_site.admin_view(self.health_check_view),
                name='tenants_postgresserver_health_check'
            ),
        ]
        return custom_urls + urls
    
    def create_docker_server_view(self, request):
        """View for creating a new Docker PostgreSQL container."""
        if request.method == 'POST':
            form = DockerServerForm(request.POST)
            if form.is_valid():
                try:
                    docker_service = DockerService()
                    server = docker_service.create_postgres_container(
                        name=form.cleaned_data['name'],
                        description=form.cleaned_data['description'],
                        container_name=form.cleaned_data['container_name'],
                        port=form.cleaned_data['port'],
                        postgres_password=form.cleaned_data['postgres_password'],
                        max_databases=form.cleaned_data['max_databases'],
                        created_by=request.user
                    )
                    
                    messages.success(
                        request,
                        f'Docker PostgreSQL server "{server.name}" created successfully!'
                    )
                    return redirect('admin:tenants_postgresserver_changelist')
                    
                except Exception as e:
                    messages.error(request, f'Error creating Docker container: {str(e)}')
        else:
            form = DockerServerForm()
        
        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': 'Create Docker PostgreSQL Server',
            'opts': self.model._meta,
        }
        return render(request, 'admin/tenants/postgresserver/create_docker.html', context)
    
    def start_server_view(self, request, server_id):
        """Start a Docker PostgreSQL server."""
        server = get_object_or_404(PostgresServer, pk=server_id)
        
        if server.server_type != 'docker':
            messages.error(request, 'Can only start Docker servers.')
            return redirect('admin:tenants_postgresserver_changelist')
        
        try:
            docker_service = DockerService()
            docker_service.start_container(server)
            messages.success(request, f'Server {server.name} started.')
        except Exception as e:
            messages.error(request, f'Error starting server: {str(e)}')
        
        return redirect('admin:tenants_postgresserver_changelist')
    
    def stop_server_view(self, request, server_id):
        """Stop a Docker PostgreSQL server."""
        server = get_object_or_404(PostgresServer, pk=server_id)
        
        if server.server_type != 'docker':
            messages.error(request, 'Can only stop Docker servers.')
            return redirect('admin:tenants_postgresserver_changelist')
        
        try:
            docker_service = DockerService()
            docker_service.stop_container(server)
            messages.success(request, f'Server {server.name} stopped.')
        except Exception as e:
            messages.error(request, f'Error stopping server: {str(e)}')
        
        return redirect('admin:tenants_postgresserver_changelist')
    
    def health_check_view(self, request, server_id):
        """Perform health check on a server."""
        server = get_object_or_404(PostgresServer, pk=server_id)
        
        try:
            db_service = DatabaseService()
            is_healthy, message = db_service.check_server_health(server)
            
            if is_healthy:
                messages.success(request, f'Server {server.name} is healthy!')
            else:
                messages.warning(request, f'Server {server.name}: {message}')
        except Exception as e:
            messages.error(request, f'Health check failed: {str(e)}')
        
        return redirect('admin:tenants_postgresserver_changelist')
    
    @admin.action(description='Check health of selected servers')
    def check_server_health(self, request, queryset):
        db_service = DatabaseService()
        for server in queryset:
            try:
                db_service.check_server_health(server)
            except Exception:
                pass
        messages.success(request, 'Health check completed.')
    
    @admin.action(description='Start selected Docker containers')
    def start_docker_containers(self, request, queryset):
        docker_service = DockerService()
        for server in queryset.filter(server_type='docker'):
            try:
                docker_service.start_container(server)
            except Exception:
                pass
        messages.success(request, 'Start command sent to Docker containers.')
    
    @admin.action(description='Stop selected Docker containers')
    def stop_docker_containers(self, request, queryset):
        docker_service = DockerService()
        for server in queryset.filter(server_type='docker'):
            try:
                docker_service.stop_container(server)
            except Exception:
                pass
        messages.success(request, 'Stop command sent to Docker containers.')


# =============================================================================
# Tenant Database Admin
# =============================================================================

@admin.register(TenantDatabase)
class TenantDatabaseAdmin(admin.ModelAdmin):
    """Admin interface for tenant databases."""
    
    list_display = [
        'display_name', 'name', 'server_link', 'status_badge',
        'assigned_users_count', 'is_migrated', 'created_at'
    ]
    list_filter = ['status', 'is_migrated', 'server', 'created_at']
    search_fields = ['name', 'display_name', 'server__name']
    readonly_fields = [
        'id', 'db_username', 'db_password', 'is_migrated',
        'last_migration', 'migrated_at', 'created_at', 'updated_at', 'created_by'
    ]
    
    fieldsets = (
        ('Database Information', {
            'fields': ('server', 'name', 'display_name', 'status')
        }),
        ('Credentials', {
            'fields': ('db_username', 'db_password'),
            'classes': ('collapse',)
        }),
        ('Migration Status', {
            'fields': ('is_migrated', 'last_migration', 'migrated_at'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['run_migrations', 'delete_databases']
    
    def server_link(self, obj):
        url = reverse('admin:tenants_postgresserver_change', args=[obj.server.pk])
        return format_html('<a href="{}">{}</a>', url, obj.server.name)
    server_link.short_description = 'Server'
    
    def status_badge(self, obj):
        colors = {
            'creating': 'info',
            'active': 'success',
            'suspended': 'warning',
            'deleting': 'danger',
            'deleted': 'secondary',
            'error': 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def assigned_users_count(self, obj):
        count = obj.assignments.filter(is_active=True).count()
        return count
    assigned_users_count.short_description = 'Users'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:db_id>/migrate/',
                self.admin_site.admin_view(self.migrate_database_view),
                name='tenants_tenantdatabase_migrate'
            ),
        ]
        return custom_urls + urls
    
    def migrate_database_view(self, request, db_id):
        """Run migrations on a tenant database."""
        tenant_db = get_object_or_404(TenantDatabase, pk=db_id)
        
        try:
            db_service = DatabaseService()
            db_service.run_migrations(tenant_db)
            messages.success(request, f'Migrations completed for {tenant_db.name}')
        except Exception as e:
            messages.error(request, f'Migration failed: {str(e)}')
        
        return redirect('admin:tenants_tenantdatabase_changelist')
    
    @admin.action(description='Run migrations on selected databases')
    def run_migrations(self, request, queryset):
        db_service = DatabaseService()
        success = 0
        failed = 0
        for db in queryset.filter(status='active'):
            try:
                db_service.run_migrations(db)
                success += 1
            except Exception:
                failed += 1
        messages.success(request, f'Migrations: {success} successful, {failed} failed.')


# =============================================================================
# Database Assignment Admin
# =============================================================================

class DatabaseAssignmentAdminForm(forms.ModelForm):
    """
    Custom form for DatabaseAssignment that allows creating a new database
    on the fly OR selecting an existing one.
    """

    # ---- extra fields for "Create new database" path -------------------------
    create_new_database = forms.BooleanField(
        required=False,
        initial=True,
        label='Create a new database',
        help_text='Uncheck to pick an existing database instead.',
        widget=forms.CheckboxInput(attrs={'id': 'id_create_new_database'}),
    )
    server = forms.ModelChoiceField(
        queryset=PostgresServer.objects.filter(status='active'),
        required=False,
        label='Server',
        help_text='Server where the new database will be created.',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    database_name = forms.CharField(
        max_length=63,
        required=False,
        label='Database name',
        help_text='Leave blank to auto-generate from the user\'s email.',
        widget=forms.TextInput(attrs={'class': 'vTextField'}),
    )

    class Meta:
        model = DatabaseAssignment
        fields = ['user', 'database', 'role', 'assigned_by']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show ALL databases (any status) so the admin sees them
        self.fields['database'].queryset = TenantDatabase.objects.all()
        self.fields['database'].required = False  # not required when creating new

        # Pre-select the first active server if available
        active_servers = PostgresServer.objects.filter(status='active')
        if active_servers.exists():
            self.fields['server'].initial = active_servers.first().pk

    def clean(self):
        cleaned = super().clean()
        create_new = cleaned.get('create_new_database')

        if create_new:
            # Need a server to create on
            if not cleaned.get('server'):
                self.add_error('server', 'Select a server for the new database.')
        else:
            # Need an existing database
            if not cleaned.get('database'):
                self.add_error('database', 'Select a database or check "Create a new database".')

        if not cleaned.get('user'):
            self.add_error('user', 'Select a user.')

        return cleaned


@admin.register(DatabaseAssignment)
class DatabaseAssignmentAdmin(admin.ModelAdmin):
    """Admin interface for database assignments."""

    form = DatabaseAssignmentAdminForm

    list_display = [
        'user_link', 'database_link', 'role', 'is_active', 'assigned_at', 'assigned_by'
    ]
    list_filter = ['role', 'is_active', 'assigned_at']
    search_fields = ['user__email', 'database__name']
    readonly_fields = ['id', 'assigned_at', 'deactivated_at']

    # Fieldsets shown when *adding* -----------------------------------------------
    add_fieldsets = (
        ('User', {
            'fields': ('user',),
        }),
        ('Database', {
            'fields': ('create_new_database', 'server', 'database_name', 'database'),
            'description': (
                'Check <strong>Create a new database</strong> to provision a '
                'fresh database on the selected server (recommended for new '
                'tenants). Uncheck to assign the user to an existing database.'
            ),
        }),
        ('Role', {
            'fields': ('role',),
        }),
    )

    # Fieldsets shown when *editing* an existing assignment -------------------------
    fieldsets = (
        (None, {
            'fields': ('user', 'database', 'role', 'is_active'),
        }),
        ('Metadata', {
            'fields': ('id', 'assigned_at', 'assigned_by', 'deactivated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return self.readonly_fields

    # ---- Custom add_view: handles DB creation + assignment atomically --------
    def add_view(self, request, form_url='', extra_context=None):
        """
        Override add_view so we fully control the POST flow.

        We never let Django's default save path run for POST requests —
        all error paths redirect back to the add page (GET) so the
        standard admin code never tries to save an incomplete object.
        """
        if request.method != 'POST':
            return super().add_view(request, form_url, extra_context)

        # Build the form the same way the admin would
        FormClass = self.get_form(request, change=False)
        form = FormClass(request.POST)

        if not form.is_valid():
            # Collect all form errors into a single message and redirect
            # (we can't call super().add_view on POST — it would re-save)
            error_msgs = '; '.join(
                f'{field}: {", ".join(errs)}' if field != '__all__' else ', '.join(errs)
                for field, errs in form.errors.items()
            )
            messages.error(request, f'Please fix the following errors: {error_msgs}')
            return redirect(request.path)

        # ---- Form is valid — process it ourselves ----------------------------
        create_new = form.cleaned_data.get('create_new_database')
        user = form.cleaned_data['user']
        role = form.cleaned_data.get('role', 'owner')
        tenant_db = None

        if create_new:
            server = form.cleaned_data['server']
            db_name = form.cleaned_data.get('database_name', '').strip()
            display_name = (
                f"{user.company_name or user.get_full_name()}'s Database"
            )
            try:
                db_service = DatabaseService()
                tenant_db = db_service.create_tenant_database(
                    server=server,
                    name=db_name or None,
                    display_name=display_name,
                    created_by=request.user,
                )
                messages.success(
                    request,
                    f'Database "{tenant_db.name}" created & migrated '
                    f'on {server.name}.'
                )
            except Exception as e:
                messages.error(
                    request, f'Failed to create database: {e}'
                )
                return redirect(request.path)
        else:
            tenant_db = form.cleaned_data.get('database')
            if tenant_db and not tenant_db.is_migrated:
                try:
                    db_service = DatabaseService()
                    db_service.run_migrations(tenant_db)
                    messages.success(
                        request,
                        f'ERP tables created in "{tenant_db.name}".'
                    )
                except Exception as e:
                    messages.warning(
                        request,
                        f'Database assigned but migration failed: {e}'
                    )

        if not tenant_db:
            messages.error(request, 'No database selected or created.')
            return redirect(request.path)

        # Ensure the user (and admin) exist in the tenant DB for FK integrity
        from tenants.services.database_service import sync_user_to_tenant_db
        from tenants.routers import add_tenant_database as _add_db
        _alias = _add_db(tenant_db)
        try:
            sync_user_to_tenant_db(user, _alias)
            if request.user.pk != user.pk:
                sync_user_to_tenant_db(request.user, _alias)
        except Exception as sync_err:
            logger.warning(f'User sync warning: {sync_err}')

        # Deactivate previous active assignments for this user
        DatabaseAssignment.objects.filter(
            user=user, is_active=True
        ).update(is_active=False, deactivated_at=timezone.now())

        # Create the assignment
        DatabaseAssignment.objects.create(
            user=user,
            database=tenant_db,
            role=role,
            assigned_by=request.user,
            is_active=True,
        )

        # Auto-approve the user if not already approved
        if not user.is_approved:
            user.approve(request.user)
            messages.info(request, f'{user.email} has been auto-approved.')

        messages.success(
            request,
            f'{user.email} assigned to "{tenant_db.display_name or tenant_db.name}".'
        )
        return redirect('admin:tenants_databaseassignment_changelist')

    # ---- JS to toggle "new database" vs "existing database" fields -----------
    class Media:
        js = ('admin/js/assignment_toggle.js',)

    def user_link(self, obj):
        url = reverse('admin:tenants_tenantuser_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'

    def database_link(self, obj):
        if not obj.database_id:
            return format_html('<span class="text-muted">—</span>')
        url = reverse('admin:tenants_tenantdatabase_change', args=[obj.database.pk])
        return format_html('<a href="{}">{}</a>', url, obj.database.name)
    database_link.short_description = 'Database'


# =============================================================================
# Server Log Admin
# =============================================================================

@admin.register(ServerLog)
class ServerLogAdmin(admin.ModelAdmin):
    """Admin interface for server logs."""
    
    list_display = ['created_at', 'level_badge', 'action', 'server', 'database', 'message_truncated']
    list_filter = ['level', 'action', 'created_at']
    search_fields = ['message', 'server__name', 'database__name']
    readonly_fields = ['id', 'created_at', 'details']
    
    def level_badge(self, obj):
        colors = {
            'info': 'info',
            'warning': 'warning',
            'error': 'danger',
            'success': 'success',
        }
        color = colors.get(obj.level, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.level.upper()
        )
    level_badge.short_description = 'Level'
    
    def message_truncated(self, obj):
        if len(obj.message) > 100:
            return obj.message[:100] + '...'
        return obj.message
    message_truncated.short_description = 'Message'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
