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
        ('database_update', 'Database Updated'),
        ('database_backup', 'Database Backup'),
        ('database_restore', 'Database Restore'),
        ('database_clone', 'Database Cloned'),
        ('database_maintenance', 'Database Maintenance'),
        ('user_assign', 'User Assigned'),
        ('user_unassign', 'User Unassigned'),
        ('docker_pull', 'Docker Image Pulled'),
        ('docker_container_create', 'Docker Container Created'),
        ('docker_container_start', 'Docker Container Started'),
        ('docker_container_stop', 'Docker Container Stopped'),
        ('docker_container_remove', 'Docker Container Removed'),
        ('docker_container_restart', 'Docker Container Restarted'),
        ('docker_container_update', 'Docker Container Resources Updated'),
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


def _generate_invite_token():
    """Generate a URL-safe random token for employee invite links."""
    return secrets.token_urlsafe(32)


class EmployeeInviteLink(models.Model):
    """
    Public invitation link that lets employees self-register into a
    specific tenant database.

    Stored in the **default** database because it references
    ``TenantDatabase`` and ``TenantUser``.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(
        max_length=64,
        unique=True,
        default=_generate_invite_token,
        db_index=True,
    )
    database = models.ForeignKey(
        TenantDatabase,
        on_delete=models.CASCADE,
        related_name='employee_invite_links',
    )
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name='employee_invite_links',
    )

    # Cached for display on the public registration page
    company_name = models.CharField(max_length=255, blank=True)
    company_name_ar = models.CharField(max_length=255, blank=True)

    is_active = models.BooleanField(default=True)
    max_registrations = models.PositiveIntegerField(
        default=0,
        help_text='Maximum number of registrations allowed (0 = unlimited)',
    )
    registration_count = models.PositiveIntegerField(default=0)

    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Leave blank for no expiry',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Employee Invite Link'
        verbose_name_plural = 'Employee Invite Links'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} invite ({self.token[:8]}…)"

    @property
    def is_valid(self):
        """Check if link is still usable."""
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.max_registrations and self.registration_count >= self.max_registrations:
            return False
        return True

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('tenants:employee_register', args=[self.token])


# ═══════════════════════════════════════════════════════════════════════════════
# Scheduled Tasks
# ═══════════════════════════════════════════════════════════════════════════════

class ScheduledTask(models.Model):
    """
    Admin-configurable recurring task:
    automated backups, VACUUM, health checks, metric collection, etc.
    """

    TASK_TYPE_CHOICES = [
        ('backup', 'Database Backup'),
        ('vacuum', 'VACUUM'),
        ('vacuum_full', 'VACUUM FULL'),
        ('analyze', 'ANALYZE'),
        ('vacuum_analyze', 'VACUUM + ANALYZE'),
        ('reindex', 'REINDEX'),
        ('health_check', 'Server Health Check'),
        ('metric_snapshot', 'Collect Metrics Snapshot'),
    ]

    INTERVAL_CHOICES = [
        ('every_30m', 'Every 30 minutes'),
        ('hourly', 'Every hour'),
        ('every_6h', 'Every 6 hours'),
        ('every_12h', 'Every 12 hours'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    task_type = models.CharField(max_length=30, choices=TASK_TYPE_CHOICES)
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, default='daily')

    # Target – at least one should be set
    server = models.ForeignKey(
        PostgresServer, on_delete=models.CASCADE,
        null=True, blank=True, related_name='scheduled_tasks',
    )
    database = models.ForeignKey(
        TenantDatabase, on_delete=models.CASCADE,
        null=True, blank=True, related_name='scheduled_tasks',
    )

    # When to run (24-h format, 0-23)
    run_at_hour = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        help_text='Hour of day to run (UTC, 0-23)',
    )
    run_at_minute = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(59)],
        help_text='Minute of hour (0-59)',
    )
    # For weekly tasks
    run_on_day = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text='Day of week (0=Mon … 6=Sun), used for weekly tasks',
    )

    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, blank=True)  # success / error
    last_message = models.TextField(blank=True)
    run_count = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        TenantUser, on_delete=models.SET_NULL,
        null=True, related_name='created_scheduled_tasks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Scheduled Task'
        verbose_name_plural = 'Scheduled Tasks'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_task_type_display()} – {self.get_interval_display()})"


class TaskExecution(models.Model):
    """Audit log for every scheduled-task run."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        ScheduledTask, on_delete=models.CASCADE, related_name='executions',
    )
    status = models.CharField(max_length=20)   # success / error / skipped
    message = models.TextField(blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.task.name} @ {self.started_at:%Y-%m-%d %H:%M} – {self.status}"


# ═══════════════════════════════════════════════════════════════════════════════
# Alerts & Notifications
# ═══════════════════════════════════════════════════════════════════════════════

class AlertRule(models.Model):
    """
    Defines a condition that triggers an alert.
    e.g. "CPU > 90 % for 5 min", "connections > 50", "disk > 80 %".
    """

    METRIC_CHOICES = [
        ('cpu_usage', 'CPU Usage %'),
        ('memory_usage', 'Memory Usage %'),
        ('disk_usage', 'Disk Usage %'),
        ('connection_count', 'Active Connections'),
        ('db_size_mb', 'Database Size (MB)'),
        ('long_queries', 'Long-Running Queries'),
        ('server_down', 'Server Down'),
        ('backup_failed', 'Backup Failed'),
        ('replication_lag', 'Replication Lag (s)'),
    ]

    OPERATOR_CHOICES = [
        ('gt', 'Greater than'),
        ('gte', 'Greater than or equal'),
        ('lt', 'Less than'),
        ('lte', 'Less than or equal'),
        ('eq', 'Equal to'),
    ]

    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    CHANNEL_CHOICES = [
        ('dashboard', 'Dashboard Only'),
        ('email', 'Email'),
        ('webhook', 'Webhook'),
        ('email_webhook', 'Email + Webhook'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    metric = models.CharField(max_length=30, choices=METRIC_CHOICES)
    operator = models.CharField(max_length=5, choices=OPERATOR_CHOICES, default='gt')
    threshold = models.FloatField(help_text='Threshold value for the alert')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning')

    # Optional target scope – blank means "all servers"
    server = models.ForeignKey(
        PostgresServer, on_delete=models.CASCADE,
        null=True, blank=True, related_name='alert_rules',
    )
    database = models.ForeignKey(
        TenantDatabase, on_delete=models.CASCADE,
        null=True, blank=True, related_name='alert_rules',
    )

    # Notification channel
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='dashboard')
    email_recipients = models.TextField(
        blank=True, help_text='Comma-separated emails for email channel',
    )
    webhook_url = models.URLField(blank=True, help_text='URL for webhook channel')

    # Cooldown – don't re-fire within N minutes
    cooldown_minutes = models.PositiveIntegerField(
        default=30,
        help_text='Minimum minutes between repeated alerts',
    )

    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        TenantUser, on_delete=models.SET_NULL,
        null=True, related_name='created_alert_rules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Alert Rule'
        verbose_name_plural = 'Alert Rules'
        ordering = ['-severity', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_metric_display()} {self.get_operator_display()} {self.threshold})"


class Alert(models.Model):
    """An individual fired alert instance."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(
        AlertRule, on_delete=models.CASCADE, related_name='alerts',
    )
    severity = models.CharField(max_length=10, choices=AlertRule.SEVERITY_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    message = models.TextField()
    metric_value = models.FloatField(null=True, blank=True)

    server = models.ForeignKey(
        PostgresServer, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alerts',
    )
    database = models.ForeignKey(
        TenantDatabase, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alerts',
    )

    acknowledged_by = models.ForeignKey(
        TenantUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='acknowledged_alerts',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.severity.upper()}] {self.message[:80]}"


# ═══════════════════════════════════════════════════════════════════════════════
# Tenant Quotas & Usage Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class TenantQuota(models.Model):
    """
    Resource limits for a tenant database.
    Quotas are checked when relevant operations occur.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    database = models.OneToOneField(
        TenantDatabase, on_delete=models.CASCADE, related_name='quota',
    )

    # Limits (0 = unlimited)
    max_db_size_mb = models.PositiveIntegerField(
        default=0, help_text='Max database size in MB (0 = unlimited)',
    )
    max_connections = models.PositiveIntegerField(
        default=0, help_text='Max concurrent connections (0 = unlimited)',
    )
    max_tables = models.PositiveIntegerField(
        default=0, help_text='Max tables allowed (0 = unlimited)',
    )
    max_storage_mb = models.PositiveIntegerField(
        default=0, help_text='Max total storage including indexes (0 = unlimited)',
    )

    # Current usage (updated by metric collection)
    current_db_size_mb = models.FloatField(default=0)
    current_connections = models.PositiveIntegerField(default=0)
    current_tables = models.PositiveIntegerField(default=0)
    current_storage_mb = models.FloatField(default=0)

    # Warning thresholds (percentage of limit)
    warning_threshold = models.PositiveIntegerField(
        default=80, help_text='Warn at this % of any limit',
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )

    last_checked = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tenant Quota'
        verbose_name_plural = 'Tenant Quotas'

    def __str__(self):
        return f"Quota for {self.database}"

    def size_usage_pct(self):
        if not self.max_db_size_mb:
            return 0
        return round(self.current_db_size_mb / self.max_db_size_mb * 100, 1)

    def connection_usage_pct(self):
        if not self.max_connections:
            return 0
        return round(self.current_connections / self.max_connections * 100, 1)

    def is_over_limit(self):
        if self.max_db_size_mb and self.current_db_size_mb > self.max_db_size_mb:
            return True
        if self.max_connections and self.current_connections > self.max_connections:
            return True
        return False

    def is_warning(self):
        pct = self.warning_threshold
        if self.max_db_size_mb and self.size_usage_pct() >= pct:
            return True
        if self.max_connections and self.connection_usage_pct() >= pct:
            return True
        return False


class UsageSnapshot(models.Model):
    """
    Point-in-time usage record for trend charts.
    Collected periodically by a scheduled task.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    database = models.ForeignKey(
        TenantDatabase, on_delete=models.CASCADE, related_name='usage_snapshots',
    )
    db_size_mb = models.FloatField(default=0)
    connections = models.PositiveIntegerField(default=0)
    table_count = models.PositiveIntegerField(default=0)
    dead_tuples = models.BigIntegerField(default=0)
    cache_hit_ratio = models.FloatField(default=0)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['database', '-recorded_at']),
        ]

    def __str__(self):
        return f"{self.database} @ {self.recorded_at:%Y-%m-%d %H:%M}"


# ═══════════════════════════════════════════════════════════════════════════════
# System Announcements
# ═══════════════════════════════════════════════════════════════════════════════

class Announcement(models.Model):
    """
    System-wide or targeted announcements for tenants.
    Displayed in banners, dashboards, or notification panels.
    """

    TYPE_CHOICES = [
        ('info', 'Informational'),
        ('warning', 'Warning'),
        ('critical', 'Critical / Outage'),
        ('maintenance', 'Planned Maintenance'),
        ('update', 'System Update'),
    ]

    AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('admins', 'Platform Admins Only'),
        ('tenants', 'Tenant Owners Only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    body = models.TextField(help_text='Supports Markdown / plain text')
    announcement_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='info')
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='all')

    is_active = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False, help_text='Pin to top of list')

    # Optional scheduling
    starts_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Start showing at this time (blank = immediately)',
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text='Stop showing after this time (blank = never)',
    )

    created_by = models.ForeignKey(
        TenantUser, on_delete=models.SET_NULL,
        null=True, related_name='created_announcements',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"[{self.get_announcement_type_display()}] {self.title}"

    @property
    def is_visible(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        return True


class AnnouncementDismissal(models.Model):
    """Tracks which users dismissed which announcements."""

    user = models.ForeignKey(
        TenantUser, on_delete=models.CASCADE, related_name='dismissed_announcements',
    )
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name='dismissals',
    )
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'announcement']


# ═══════════════════════════════════════════════════════════════════════════════
# Monitoring / Metric History
# ═══════════════════════════════════════════════════════════════════════════════

class MetricSnapshot(models.Model):
    """
    Server-level metric snapshot for historical monitoring charts.
    Captured periodically (every 5–30 min).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    server = models.ForeignKey(
        PostgresServer, on_delete=models.CASCADE, related_name='metric_snapshots',
    )

    # Docker / OS metrics
    cpu_percent = models.FloatField(default=0)
    memory_percent = models.FloatField(default=0)
    memory_used_mb = models.FloatField(default=0)
    memory_limit_mb = models.FloatField(default=0)
    disk_used_mb = models.FloatField(default=0)
    disk_total_mb = models.FloatField(default=0)
    net_rx_mb = models.FloatField(default=0)
    net_tx_mb = models.FloatField(default=0)

    # PostgreSQL metrics
    total_connections = models.PositiveIntegerField(default=0)
    active_connections = models.PositiveIntegerField(default=0)
    total_db_size_mb = models.FloatField(default=0)
    cache_hit_ratio = models.FloatField(default=0)
    transactions_per_sec = models.FloatField(default=0)

    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['server', '-recorded_at']),
        ]

    def __str__(self):
        return f"{self.server.name} @ {self.recorded_at:%Y-%m-%d %H:%M}"
