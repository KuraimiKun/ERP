"""
ERP Admin – Services models
"""

from django.contrib import admin
from erp.models import (
    ServiceCategory,
    ServicePricing,
    ServicePackage,
    PackageItem,
    Quote,
    QuoteLine,
)
from .mixins import CompanyIsolatedAdmin, CompanyIsolatedInline


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(CompanyIsolatedAdmin):
    list_display = ["name", "code", "parent", "is_active"]
    list_filter = ["company", "is_active"]
    search_fields = ["name", "code"]


@admin.register(ServicePricing)
class ServicePricingAdmin(CompanyIsolatedAdmin):
    list_display = ["code", "name", "category", "pricing_type", "base_price", "cost_price", "is_active"]
    list_filter = ["category", "pricing_type", "is_active"]
    search_fields = ["code", "name"]


class PackageItemInline(CompanyIsolatedInline):
    model = PackageItem
    extra = 1


@admin.register(ServicePackage)
class ServicePackageAdmin(CompanyIsolatedAdmin):
    list_display = ["code", "name", "regular_price", "package_price", "is_active", "is_featured"]
    list_filter = ["is_active", "is_featured"]
    search_fields = ["code", "name"]
    inlines = [PackageItemInline]


class QuoteLineInline(CompanyIsolatedInline):
    model = QuoteLine
    extra = 1


@admin.register(Quote)
class QuoteAdmin(CompanyIsolatedAdmin):
    list_display = ["quote_number", "customer", "quote_date", "valid_until", "total_amount", "status"]
    list_filter = ["status", "quote_date"]
    search_fields = ["quote_number", "customer__name"]
    date_hierarchy = "quote_date"
    inlines = [QuoteLineInline]
