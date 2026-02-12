"""
Admin Configuration for Tenant Management

Provides comprehensive admin interface for managing:
- Users and their approval workflow
- PostgreSQL servers (remote and Docker)
- Tenant databases
- Database assignments
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse

from .models import (
    TenantUser, PostgresServer, TenantDatabase,
    DatabaseAssignment, ServerLog
)
from .forms import UserApprovalForm, UserRejectionForm, DockerServerForm, UserAssignExistingDatabaseForm
from .services.database_service import DatabaseService
from .services.docker_service import DockerService


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
        messages.success(request, f'Users approved. Remember to assign databases.')
    
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

@admin.register(PostgresServer)
class PostgresServerAdmin(admin.ModelAdmin):
    """Admin interface for PostgreSQL servers."""
    
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
    
    actions = ['check_server_health', 'start_docker_containers', 'stop_docker_containers']
    
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

@admin.register(DatabaseAssignment)
class DatabaseAssignmentAdmin(admin.ModelAdmin):
    """Admin interface for database assignments."""
    
    list_display = [
        'user_link', 'database_link', 'role', 'is_active', 'assigned_at', 'assigned_by'
    ]
    list_filter = ['role', 'is_active', 'assigned_at']
    search_fields = ['user__email', 'database__name']
    readonly_fields = ['id', 'assigned_at', 'deactivated_at']
    
    def user_link(self, obj):
        url = reverse('admin:tenants_tenantuser_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    
    def database_link(self, obj):
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
