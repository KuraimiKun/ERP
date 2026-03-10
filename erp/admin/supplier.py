"""
ERP Admin – Supplier / Procurement models
"""

from django.contrib import admin
from erp.models import (
    Supplier, SupplierContact, SupplierDocument,
    PurchaseOrder, PurchaseOrderLine,
    SupplierInvoice, SupplierInvoiceLine,
    SupplierPayment,
)


class SupplierContactInline(admin.TabularInline):
    model = SupplierContact
    extra = 0


class SupplierDocumentInline(admin.TabularInline):
    model = SupplierDocument
    extra = 0


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['supplier_id', 'name', 'supplier_type', 'email', 'phone', 'current_balance', 'is_active']
    list_filter = ['company', 'supplier_type', 'is_active']
    search_fields = ['supplier_id', 'name', 'email']
    inlines = [SupplierContactInline, SupplierDocumentInline]


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['po_number', 'supplier', 'po_date', 'total_amount', 'status']
    list_filter = ['status', 'po_date']
    search_fields = ['po_number', 'supplier__name']
    date_hierarchy = 'po_date'
    inlines = [PurchaseOrderLineInline]


class SupplierInvoiceLineInline(admin.TabularInline):
    model = SupplierInvoiceLine
    extra = 1


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'supplier', 'invoice_date', 'due_date', 'total_amount', 'balance_due', 'status']
    list_filter = ['status', 'invoice_date']
    search_fields = ['invoice_number', 'supplier__name']
    date_hierarchy = 'invoice_date'
    inlines = [SupplierInvoiceLineInline]


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_number', 'supplier', 'payment_date', 'amount', 'allocated_amount']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['payment_number', 'supplier__name']
    date_hierarchy = 'payment_date'
