"""
ERP Admin – Reporting models
"""

from django.contrib import admin
from erp.models import (
    ReportTemplate,
    GeneratedReport,
    Dashboard,
    KPI,
)
from .mixins import CompanyIsolatedAdmin


@admin.register(ReportTemplate)
class ReportTemplateAdmin(CompanyIsolatedAdmin):
    list_display = ["name", "report_type", "default_format", "is_public", "is_active"]
    list_filter = ["report_type", "is_public", "is_active"]
    search_fields = ["name"]


@admin.register(GeneratedReport)
class GeneratedReportAdmin(CompanyIsolatedAdmin):
    company_lookup = "template__company"
    list_display = ["template", "generated_by", "date_from", "date_to", "output_format", "is_ready", "created_at"]
    list_filter = ["template", "output_format", "is_ready"]
    date_hierarchy = "created_at"


@admin.register(Dashboard)
class DashboardAdmin(CompanyIsolatedAdmin):
    list_display = ["name", "owner", "is_default", "is_public"]
    list_filter = ["is_default", "is_public"]
    search_fields = ["name"]


@admin.register(KPI)
class KPIAdmin(CompanyIsolatedAdmin):
    list_display = ["name", "kpi_type", "target_value", "unit", "is_active"]
    list_filter = ["kpi_type", "is_active"]
    search_fields = ["name"]
