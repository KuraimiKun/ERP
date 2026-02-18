"""
Tenant Management Models

This module defines models for multi-tenant database management:
- TenantUser: Custom user model with approval workflow
- PostgresServer: PostgreSQL server instances (remote or Docker)
- TenantDatabase: Individual tenant databases
- DatabaseAssignment: Links users to their assigned databases
"""

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import secrets
import string


class TenantUserManager(BaseUserManager):
    """Custom manager for TenantUser model."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_approved', True)
        extra_fields.setdefault('approval_status', 'approved')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class TenantUser(AbstractUser):
    """
    Custom user model for tenant management.
    
    Users sign up and wait for admin approval before being assigned
    to a PostgreSQL database.
    """
    
    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    
    # Remove username field, use email as primary identifier
    username = None
    email = models.EmailField('Email Address', unique=True)
    
    # Profile fields
    company_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Approval workflow
    is_approved = models.BooleanField(default=False)
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending'
    )
    approved_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_users'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = TenantUserManager()
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def approve(self, approved_by):
        """Approve the user account."""
        self.is_approved = True
        self.approval_status = 'approved'
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.save()
    
    def reject(self, reason=''):
        """Reject the user account."""
        self.is_approved = False
        self.approval_status = 'rejected'
        self.rejection_reason = reason
        self.save()
    
    def suspend(self):
        """Suspend the user account."""
        self.is_approved = False
        self.approval_status = 'suspended'
        self.is_active = False
        self.save()
    
    @property
    def assigned_database(self):
        """Get the user's assigned database, if any."""
        assignment = self.database_assignments.filter(is_active=True).first()
        return assignment.database if assignment else None


class PostgresServer(models.Model):
    """
    PostgreSQL server instance.
    
    Can be either a remote server or a local Docker container.
    Each server can host multiple tenant databases.
    """
    
    SERVER_TYPE_CHOICES = [
        ('remote', 'Remote Server'),
        ('docker', 'Local Docker Container'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Server type
    server_type = models.CharField(
        max_length=20,
        choices=SERVER_TYPE_CHOICES,
        default='docker'
    )
    
    # Connection details
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(
        default=5432,
        validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    admin_username = models.CharField(max_length=100, default='postgres')
    admin_password = models.CharField(max_length=255)
    
    # Docker-specific fields
    docker_container_id = models.CharField(max_length=64, blank=True)
    docker_container_name = models.CharField(max_length=100, blank=True)
    docker_volume_name = models.CharField(max_length=100, blank=True)
    
    # Capacity
    max_databases = models.PositiveIntegerField(
        default=50,
        help_text='Maximum number of databases this server can host'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='inactive'
    )
    last_health_check = models.DateTimeField(null=True, blank=True)
    health_check_message = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_servers'
    )
    
    class Meta:
        verbose_name = 'PostgreSQL Server'
        verbose_name_plural = 'PostgreSQL Servers'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_server_type_display()})"
    
    @property
    def database_count(self):
        """Get the number of databases on this server."""
        return self.databases.count()
    
    @property
    def available_slots(self):
        """Get the number of available database slots."""
        return max(0, self.max_databases - self.database_count)
    
    @property
    def is_full(self):
        """Check if the server has reached its database limit."""
        return self.database_count >= self.max_databases
    
    @property
    def connection_string(self):
        """Get the base connection string for this server."""
        return f"postgresql://{self.admin_username}:{self.admin_password}@{self.host}:{self.port}"


def generate_db_password():
    """Generate a secure random password for database access."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(24))


class TenantDatabase(models.Model):
    """
    Individual tenant database.
    
    Each database belongs to a PostgreSQL server and can be assigned
    to one or more users.
    """
    
    STATUS_CHOICES = [
        ('creating', 'Creating'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('deleting', 'Deleting'),
        ('deleted', 'Deleted'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Server relationship
    server = models.ForeignKey(
        PostgresServer,
        on_delete=models.PROTECT,
        related_name='databases'
    )
    
    # Database details
    name = models.CharField(
        max_length=63,  # PostgreSQL max identifier length
        help_text='Database name (auto-generated if not provided)'
    )
    display_name = models.CharField(max_length=100, blank=True)
    
    # Database credentials
    db_username = models.CharField(max_length=63)
    db_password = models.CharField(max_length=255, default=generate_db_password)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='creating'
    )
    error_message = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_databases'
    )
    
    # Migration tracking
    is_migrated = models.BooleanField(default=False)
    last_migration = models.CharField(max_length=255, blank=True)
    migrated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Tenant Database'
        verbose_name_plural = 'Tenant Databases'
        ordering = ['-created_at']
        unique_together = [['server', 'name']]
    
    def __str__(self):
        return f"{self.display_name or self.name} on {self.server.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate database name if not provided
        if not self.name:
            self.name = f"erp_tenant_{str(self.id).replace('-', '')[:16]}"
        # Auto-generate username if not provided
        if not self.db_username:
            self.db_username = f"user_{str(self.id).replace('-', '')[:12]}"
        super().save(*args, **kwargs)
    
    @property
    def connection_config(self):
        """Get Django database configuration for this tenant.
        
        Includes all standard Django database config keys so that
        dynamically-added databases behave identically to statically
        defined ones (Django's ConnectionHandler.databases only applies
        setdefault() on initial load, not on later additions).
        """
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': self.name,
            'USER': self.db_username,
            'PASSWORD': self.db_password,
            'HOST': self.server.host,
            'PORT': str(self.server.port),
            'ATOMIC_REQUESTS': False,
            'AUTOCOMMIT': True,
            'CONN_MAX_AGE': 0,
            'CONN_HEALTH_CHECKS': False,
            'DISABLE_SERVER_SIDE_CURSORS': True,
            'OPTIONS': {},
            'TIME_ZONE': None,
            'TEST': {},
        }
    
    @property
    def connection_string(self):
        """Get the full connection string."""
        return f"postgresql://{self.db_username}:{self.db_password}@{self.server.host}:{self.server.port}/{self.name}"


class DatabaseAssignment(models.Model):
    """
    Assignment of a user to a tenant database.
    
    This allows multiple users to share the same database,
    or a user to be reassigned to a different database.
    """
    
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('user', 'User'),
        ('readonly', 'Read Only'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name='database_assignments'
    )
    database = models.ForeignKey(
        TenantDatabase,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    
    # Role within the database
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='owner'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        TenantUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='made_assignments'
    )
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Database Assignment'
        verbose_name_plural = 'Database Assignments'
        ordering = ['-assigned_at']
    
    def __str__(self):
        db_name = self.database.name if self.database_id else 'unassigned'
        return f"{self.user.email} -> {db_name} ({self.get_role_display()})"
    
    def deactivate(self):
        """Deactivate this assignment."""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save()


class ServerLog(models.Model):
    """Log entries for server and database operations."""
    
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('success', 'Success'),
    ]
    
    ACTION_CHOICES = [
        ('server_create', 'Server Created'),
        ('server_start', 'Server Started'),
        ('server_stop', 'Server Stopped'),
        ('server_delete', 'Server Deleted'),
        ('server_health_check', 'Health Check'),
        ('database_create', 'Database Created'),
        ('database_delete', 'Database Deleted'),
        ('database_migrate', 'Database Migrated'),
        ('user_assign', 'User Assigned'),
        ('user_unassign', 'User Unassigned'),
        ('docker_pull', 'Docker Image Pulled'),
        ('docker_container_create', 'Docker Container Created'),
        ('docker_container_start', 'Docker Container Started'),
        ('docker_container_stop', 'Docker Container Stopped'),
        ('docker_container_remove', 'Docker Container Removed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Related objects
    server = models.ForeignKey(
        PostgresServer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    database = models.ForeignKey(
        TenantDatabase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    user = models.ForeignKey(
        TenantUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='server_logs'
    )
    
    # Log details
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Server Log'
        verbose_name_plural = 'Server Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"[{self.level.upper()}] {self.get_action_display()} - {self.created_at}"
