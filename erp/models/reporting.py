from django.utils.translation import gettext_lazy as _
"""
Reporting and Analytics models for the ERP system.
"""

from django.db import models
from django.conf import settings
from .base import TimeStampedModel
import uuid


def report_file_path(instance, filename):
    """Generate upload path for generated reports."""
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"
    return f'erp/reports/{new_filename}'


class ReportTemplate(TimeStampedModel):
    """Report templates for generating reports."""
    class ReportType(models.TextChoices):
        SALES = 'sales', 'Sales Report'
        REVENUE = 'revenue', 'Revenue Report'
        EXPENSE = 'expense', 'Expense Report'
        CUSTOMER = 'customer', 'Customer Report'
        SUPPLIER = 'supplier', 'Supplier Report'
        EMPLOYEE = 'employee', 'Employee Report'
        PAYROLL = 'payroll', 'Payroll Report'
        SERVICE = 'service', 'Service Report'
        FINANCIAL = 'financial', 'Financial Report'
        TAX = 'tax', 'Tax Report'
        CUSTOM = 'custom', 'Custom Report'

    class OutputFormat(models.TextChoices):
        PDF = 'pdf', 'PDF'
        EXCEL = 'excel', 'Excel'
        CSV = 'csv', 'CSV'
        HTML = 'html', 'HTML'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='report_templates'
    )
    
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=20, choices=ReportType.choices)
    description = models.TextField(blank=True)
    
    # Configuration (JSON)
    configuration = models.JSONField(default=dict, blank=True, help_text=_('Report configuration as JSON'))
    
    # Default format
    default_format = models.CharField(max_length=10, choices=OutputFormat.choices, default=OutputFormat.PDF)
    
    # Access control
    is_public = models.BooleanField(default=False, help_text=_('Available to all users'))
    allowed_roles = models.JSONField(default=list, blank=True, help_text=_('List of roles that can access this report'))
    
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text=_('System reports cannot be deleted'))

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_report_templates',
    )

    class Meta:
        verbose_name=_('Report Template')
        verbose_name_plural = 'Report Templates'
        ordering = ['report_type', 'name']

    def __str__(self):
        return self.name


class GeneratedReport(TimeStampedModel):
    """Generated report instances."""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.CASCADE,
        related_name='generated_reports'
    )
    
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_reports'
    )
    
    # Parameters used
    parameters = models.JSONField(default=dict, blank=True)
    
    # Date range
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    
    # Output
    output_format = models.CharField(max_length=10, choices=ReportTemplate.OutputFormat.choices)
    file = models.FileField(upload_to=report_file_path, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    is_ready = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    # Execution tracking
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name=_('Generated Report')
        verbose_name_plural = 'Generated Reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['generated_by', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.template.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class Dashboard(TimeStampedModel):
    """Custom dashboards."""
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='dashboards'
    )
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Owner
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_dashboards'
    )
    
    # Layout configuration
    layout = models.JSONField(default=dict, blank=True, help_text=_('Dashboard layout configuration'))
    
    # Access
    is_default = models.BooleanField(default=False, help_text=_('Show as default dashboard'))
    is_public = models.BooleanField(default=False, help_text=_('Visible to all users'))

    class Meta:
        verbose_name=_('Dashboard')
        verbose_name_plural = 'Dashboards'
        ordering = ['name']

    def __str__(self):
        return self.name


class DashboardWidget(TimeStampedModel):
    """Widgets on dashboards."""
    class WidgetType(models.TextChoices):
        COUNTER = 'counter', 'Counter/KPI'
        CHART_LINE = 'chart_line', 'Line Chart'
        CHART_BAR = 'chart_bar', 'Bar Chart'
        CHART_PIE = 'chart_pie', 'Pie Chart'
        CHART_DOUGHNUT = 'chart_doughnut', 'Doughnut Chart'
        TABLE = 'table', 'Data Table'
        LIST = 'list', 'List'
        CALENDAR = 'calendar', 'Calendar'
        MAP = 'map', 'Map'
        CUSTOM = 'custom', 'Custom Widget'

    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='widgets'
    )
    
    title = models.CharField(max_length=255)
    widget_type = models.CharField(max_length=20, choices=WidgetType.choices)
    
    # Position
    row = models.PositiveSmallIntegerField(default=0)
    column = models.PositiveSmallIntegerField(default=0)
    width = models.PositiveSmallIntegerField(default=1)
    height = models.PositiveSmallIntegerField(default=1)
    
    # Configuration
    configuration = models.JSONField(default=dict, blank=True, help_text=_('Widget configuration'))
    
    # Data source
    data_source = models.CharField(max_length=255, blank=True, help_text=_('API endpoint or query identifier'))
    refresh_interval = models.PositiveIntegerField(default=0, help_text=_('Refresh interval in seconds (0 = no auto-refresh)'))

    class Meta:
        verbose_name=_('Dashboard Widget')
        verbose_name_plural = 'Dashboard Widgets'
        ordering = ['row', 'column']

    def __str__(self):
        return f"{self.dashboard.name} - {self.title}"


class KPI(TimeStampedModel):
    """Key Performance Indicators definitions."""
    class KPIType(models.TextChoices):
        REVENUE = 'revenue', 'Revenue'
        SALES = 'sales', 'Sales'
        CUSTOMERS = 'customers', 'Customers'
        CONVERSION = 'conversion', 'Conversion Rate'
        EFFICIENCY = 'efficiency', 'Efficiency'
        SATISFACTION = 'satisfaction', 'Customer Satisfaction'
        CUSTOM = 'custom', 'Custom'

    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='kpis'
    )
    
    name = models.CharField(max_length=255)
    kpi_type = models.CharField(max_length=20, choices=KPIType.choices)
    description = models.TextField(blank=True)
    
    # Calculation
    calculation_query = models.TextField(blank=True, help_text=_('SQL or calculation logic'))
    unit = models.CharField(max_length=50, blank=True, help_text=_('e.g., %, $, count'))
    
    # Targets
    target_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    warning_threshold = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Is higher better or lower better?
    higher_is_better = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name=_('KPI')
        verbose_name_plural = 'KPIs'
        ordering = ['kpi_type', 'name']

    def __str__(self):
        return self.name


class KPIValue(TimeStampedModel):
    """Recorded KPI values over time."""
    kpi = models.ForeignKey(
        KPI,
        on_delete=models.CASCADE,
        related_name='values'
    )
    
    value = models.DecimalField(max_digits=15, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Comparison
    previous_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    change_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name=_('KPI Value')
        verbose_name_plural = 'KPI Values'
        ordering = ['-period_end']
        unique_together = ['kpi', 'period_start', 'period_end']

    def __str__(self):
        return f"{self.kpi.name}: {self.value} ({self.period_start} - {self.period_end})"
