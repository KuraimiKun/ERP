"""
ERP Admin – Core models
"""

from django.contrib import admin
from erp.models import Currency, Company, Department, Branch, FiscalYear, Sequence
from .mixins import CompanyIsolatedAdmin


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'exchange_rate', 'is_base', 'is_active']
    list_filter = ['is_base', 'is_active']
    search_fields = ['code', 'name']
    list_editable = ['exchange_rate', 'is_active']


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'city', 'country']
    search_fields = ['name', 'email', 'legal_name']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'name_ar', 'legal_name', 'logo', 'favicon')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'fax', 'website')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Tax & Registration', {
            'fields': ('tax_number', 'commercial_register', 'license_number')
        }),
        ('Banking', {
            'fields': ('bank_name', 'bank_account', 'iban', 'swift_code')
        }),
        ('Settings', {
            'fields': ('base_currency', 'fiscal_year_start')
        }),
    )


@admin.register(Department)
class DepartmentAdmin(CompanyIsolatedAdmin):
    list_display = ['name', 'code', 'company', 'manager', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Branch)
class BranchAdmin(CompanyIsolatedAdmin):
    list_display = ['name', 'code', 'company', 'city', 'is_headquarters', 'is_active']
    list_filter = ['company', 'is_headquarters', 'is_active']
    search_fields = ['name', 'code', 'city']


@admin.register(FiscalYear)
class FiscalYearAdmin(CompanyIsolatedAdmin):
    list_display = ['name', 'company', 'start_date', 'end_date', 'is_current', 'is_closed']
    list_filter = ['company', 'is_current', 'is_closed']
    search_fields = ['name']


@admin.register(Sequence)
class SequenceAdmin(CompanyIsolatedAdmin):
    list_display = ['sequence_type', 'company', 'prefix', 'next_number', 'padding', 'reset_period']
    list_filter = ['company', 'sequence_type', 'reset_period']
    search_fields = ['prefix']
