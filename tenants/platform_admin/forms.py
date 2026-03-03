"""
Platform Admin - Forms

Admin-specific forms separated from the public tenant forms.
"""

from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator

from tenants.models import (
    PostgresServer, TenantDatabase, TenantUser,
    DatabaseAssignment, EmployeeInviteLink,
    ScheduledTask, AlertRule, TenantQuota, Announcement,
)


class PostgresServerForm(forms.ModelForm):
    """Form for creating/editing PostgreSQL servers."""

    class Meta:
        model = PostgresServer
        fields = [
            'name', 'description', 'server_type',
            'host', 'port', 'admin_username', 'admin_password',
            'max_databases', 'status',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Server name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'server_type': forms.Select(attrs={'class': 'form-select'}),
            'host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'hostname or IP'}),
            'port': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '5432'}),
            'admin_username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'postgres'}),
            'admin_password': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
            'max_databases': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class DockerServerForm(forms.Form):
    """Form for creating a new Docker PostgreSQL container."""

    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Server name'})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description (optional)'})
    )
    container_name = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Container name (auto-generated if empty)'})
    )
    port = forms.IntegerField(
        initial=5432,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Host port (default: 5432)'})
    )
    postgres_password = forms.CharField(
        max_length=100,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'PostgreSQL admin password'})
    )
    max_databases = forms.IntegerField(
        initial=50,
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


class UserApprovalForm(forms.Form):
    """Form for approving a user and assigning them to a database."""

    server = forms.ModelChoiceField(
        queryset=PostgresServer.objects.filter(status='active'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Select a PostgreSQL server for the new database'
    )
    database_name = forms.CharField(
        max_length=63, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Database name (auto-generated if empty)'
        }),
        help_text='Leave empty to auto-generate'
    )
    display_name = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Display name for the database'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = PostgresServer.objects.filter(status='active')


class UserAssignExistingDatabaseForm(forms.Form):
    """Form for assigning a user to an existing database."""

    database = forms.ModelChoiceField(
        queryset=TenantDatabase.objects.filter(status='active'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Select an existing database'
    )
    role = forms.ChoiceField(
        choices=DatabaseAssignment.ROLE_CHOICES,
        initial='user',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class UserRejectionForm(forms.Form):
    """Form for rejecting a user application."""

    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 4,
            'placeholder': 'Reason for rejection (optional)'
        })
    )


class DatabaseForm(forms.ModelForm):
    """Form for creating a tenant database."""

    class Meta:
        model = TenantDatabase
        fields = ['server', 'name', 'display_name']
        widgets = {
            'server': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Database name (auto-generated if empty)'
            }),
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Display name'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = PostgresServer.objects.filter(status='active')
        self.fields['name'].required = False


class InviteLinkForm(forms.ModelForm):
    """Form for creating/editing employee invite links."""

    expires_days = forms.IntegerField(
        required=False, initial=0,
        help_text='Number of days until link expires (0 = never)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'placeholder': '0 for no expiry', 'min': '0'
        })
    )

    class Meta:
        model = EmployeeInviteLink
        fields = ['database', 'company_name', 'company_name_ar', 'max_registrations']
        widgets = {
            'database': forms.Select(attrs={'class': 'form-select'}),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Company name (English)'
            }),
            'company_name_ar': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Company name (Arabic)'
            }),
            'max_registrations': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': '0 for unlimited', 'min': '0'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['database'].queryset = TenantDatabase.objects.filter(status='active')


class UserEditForm(forms.ModelForm):
    """Form for admin to edit user details."""

    class Meta:
        model = TenantUser
        fields = ['first_name', 'last_name', 'email', 'company_name', 'phone', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BulkActionForm(forms.Form):
    """Form for bulk user actions."""

    ACTION_CHOICES = [
        ('approve', 'Approve Selected'),
        ('reject', 'Reject Selected'),
        ('suspend', 'Suspend Selected'),
        ('delete', 'Delete Selected'),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    reason = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Reason (for rejection)'
        })
    )


# ── Enterprise: Docker Resource Forms ────────────────────────────────────────

class DockerResourceLimitForm(forms.Form):
    """Form for updating Docker container resource limits."""

    memory_limit = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 512m, 1g, 2g',
        }),
        help_text='Memory limit (e.g. 256m, 512m, 1g, 2g)',
    )
    cpus = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 0.5, 1, 2',
        }),
        help_text='CPU count (decimal, e.g. 0.5, 1, 2)',
    )
    cpu_shares = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '1024 (default)',
        }),
        help_text='Relative CPU weight (1024 = default)',
    )


class DockerImagePullForm(forms.Form):
    """Form for pulling a Docker image."""

    image_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'postgres:16-alpine',
        }),
        help_text='Only PostgreSQL images are allowed.',
    )


# ── Enterprise: Database Operations Forms ────────────────────────────────────

class DatabaseMaintenanceForm(forms.Form):
    """Form for running database maintenance."""

    OPERATION_CHOICES = [
        ('vacuum', 'VACUUM - Reclaim storage'),
        ('vacuum_full', 'VACUUM FULL - Full compaction (locks DB)'),
        ('analyze', 'ANALYZE - Update planner statistics'),
        ('vacuum_analyze', 'VACUUM ANALYZE - Combined operation'),
        ('reindex', 'REINDEX - Rebuild all indexes'),
    ]

    operation = forms.ChoiceField(
        choices=OPERATION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class DatabaseCloneForm(forms.Form):
    """Form for cloning a database."""

    new_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'new_database_name',
        }),
        help_text='Must be a valid PostgreSQL identifier (lowercase, no spaces).',
    )
    new_display_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Display Name (optional)',
        }),
    )


class DatabaseImportForm(forms.Form):
    """Form for importing a SQL file into a database."""

    sql_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.sql,.dump,.backup',
        }),
        help_text='Upload a .sql or .dump file to restore.',
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Scheduled Tasks Forms
# ═══════════════════════════════════════════════════════════════════════════════

class ScheduledTaskForm(forms.ModelForm):
    """Form for creating/editing a scheduled task."""

    class Meta:
        model = ScheduledTask
        fields = [
            'name', 'task_type', 'interval', 'server', 'database',
            'run_at_hour', 'run_at_minute', 'run_on_day', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task name'}),
            'task_type': forms.Select(attrs={'class': 'form-select'}),
            'interval': forms.Select(attrs={'class': 'form-select'}),
            'server': forms.Select(attrs={'class': 'form-select'}),
            'database': forms.Select(attrs={'class': 'form-select'}),
            'run_at_hour': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 23}),
            'run_at_minute': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 59}),
            'run_on_day': forms.Select(
                choices=[
                    (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
                    (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
                ],
                attrs={'class': 'form-select'},
            ),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = PostgresServer.objects.filter(status='active')
        self.fields['database'].queryset = TenantDatabase.objects.filter(status='active')
        self.fields['server'].required = False
        self.fields['database'].required = False


# ═══════════════════════════════════════════════════════════════════════════════
# Alerts Forms
# ═══════════════════════════════════════════════════════════════════════════════

class AlertRuleForm(forms.ModelForm):
    """Form for creating/editing an alert rule."""

    class Meta:
        model = AlertRule
        fields = [
            'name', 'description', 'metric', 'operator', 'threshold',
            'severity', 'server', 'database',
            'channel', 'email_recipients', 'webhook_url',
            'cooldown_minutes', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Alert rule name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Description (optional)'}),
            'metric': forms.Select(attrs={'class': 'form-select'}),
            'operator': forms.Select(attrs={'class': 'form-select'}),
            'threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'e.g. 90'}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'server': forms.Select(attrs={'class': 'form-select'}),
            'database': forms.Select(attrs={'class': 'form-select'}),
            'channel': forms.Select(attrs={'class': 'form-select'}),
            'email_recipients': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'admin@example.com, ops@example.com'}),
            'webhook_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://hooks.slack.com/...'}),
            'cooldown_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = PostgresServer.objects.all()
        self.fields['database'].queryset = TenantDatabase.objects.filter(status='active')
        self.fields['server'].required = False
        self.fields['database'].required = False


# ═══════════════════════════════════════════════════════════════════════════════
# Tenant Quotas Forms
# ═══════════════════════════════════════════════════════════════════════════════

class TenantQuotaForm(forms.ModelForm):
    """Form for editing a tenant quota."""

    class Meta:
        model = TenantQuota
        fields = [
            'max_db_size_mb', 'max_connections', 'max_tables',
            'max_storage_mb', 'warning_threshold',
        ]
        widgets = {
            'max_db_size_mb': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': '0 = unlimited'}),
            'max_connections': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': '0 = unlimited'}),
            'max_tables': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': '0 = unlimited'}),
            'max_storage_mb': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': '0 = unlimited'}),
            'warning_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 99}),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Announcements Forms
# ═══════════════════════════════════════════════════════════════════════════════

class AnnouncementForm(forms.ModelForm):
    """Form for creating/editing a system announcement."""

    class Meta:
        model = Announcement
        fields = [
            'title', 'body', 'announcement_type', 'audience',
            'is_active', 'is_pinned', 'starts_at', 'expires_at',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Announcement title'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Announcement content...'}),
            'announcement_type': forms.Select(attrs={'class': 'form-select'}),
            'audience': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'starts_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'expires_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['starts_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['expires_at'].input_formats = ['%Y-%m-%dT%H:%M']

