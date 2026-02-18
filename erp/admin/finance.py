"""
ERP Admin – Finance models
"""

from django.contrib import admin
from erp.models import (
    Account, TaxRate, PaymentMethod, Customer,
    Invoice, InvoiceLine, Payment, PaymentAllocation,
    Expense, ExpenseCategory, ExpenseAttachment,
)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'current_balance', 'is_active']
    list_filter = ['company', 'account_type', 'is_active']
    search_fields = ['code', 'name']
    list_editable = ['is_active']


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ['name', 'rate', 'is_default', 'is_active']
    list_filter = ['company', 'is_default', 'is_active']


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']
    list_filter = ['company', 'is_active']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'name', 'customer_type', 'email', 'phone', 'current_balance', 'is_active']
    list_filter = ['company', 'customer_type', 'is_active']
    search_fields = ['customer_id', 'name', 'email', 'phone']


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'customer', 'invoice_date', 'due_date', 'total_amount', 'balance_due', 'status']
    list_filter = ['status', 'invoice_type', 'invoice_date']
    search_fields = ['invoice_number', 'customer__name']
    date_hierarchy = 'invoice_date'
    inlines = [InvoiceLineInline]
    readonly_fields = ['subtotal', 'tax_amount', 'total_amount', 'paid_amount', 'balance_due']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_number', 'customer', 'payment_date', 'payment_method', 'amount', 'allocated_amount']
    list_filter = ['payment_type', 'payment_method', 'payment_date']
    search_fields = ['payment_number', 'customer__name']
    date_hierarchy = 'payment_date'


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'parent', 'is_active']
    list_filter = ['company', 'is_active']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['expense_number', 'expense_date', 'category', 'total_amount', 'status']
    list_filter = ['status', 'category', 'expense_date']
    search_fields = ['expense_number', 'description']
    date_hierarchy = 'expense_date'
