"""
Forms for Tenant Management
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import TenantUser, PostgresServer, TenantDatabase, DatabaseAssignment


class SignUpForm(UserCreationForm):
    """User registration form."""
    
    email = forms.EmailField(
        max_length=255,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address'
        })
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    company_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Company name (optional)'
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone number (optional)'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )
    
    class Meta:
        model = TenantUser
        fields = ['email', 'first_name', 'last_name', 'company_name', 'phone', 'password1', 'password2']


class LoginForm(AuthenticationForm):
    """Custom login form."""
    
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )


class PostgresServerForm(forms.ModelForm):
    """Form for creating/editing PostgreSQL servers."""
    
    class Meta:
        model = PostgresServer
        fields = [
            'name', 'description', 'server_type',
            'host', 'port', 'admin_username', 'admin_password',
            'max_databases'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'server_type': forms.Select(attrs={'class': 'form-select'}),
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'admin_username': forms.TextInput(attrs={'class': 'form-control'}),
            'admin_password': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
            'max_databases': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class DockerServerForm(forms.Form):
    """Form for creating a new Docker PostgreSQL container."""
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Server name'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Description (optional)'
        })
    )
    container_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Container name (auto-generated if empty)'
        })
    )
    port = forms.IntegerField(
        initial=5432,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Host port (default: 5432)'
        })
    )
    postgres_password = forms.CharField(
        max_length=100,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'PostgreSQL admin password'
        })
    )
    max_databases = forms.IntegerField(
        initial=50,
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
        })
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
        max_length=63,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Database name (auto-generated if empty)'
        }),
        help_text='Leave empty to auto-generate'
    )
    display_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Display name for the database'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Update queryset to only show active servers with available slots
        self.fields['server'].queryset = PostgresServer.objects.filter(
            status='active'
        )


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
            'class': 'form-control',
            'rows': 4,
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
