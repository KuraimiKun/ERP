"""Quick audit of tenant database contents."""
import os

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erpproject.settings')
django.setup()

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext
from erp.models import Company, Product, Warehouse, StockMovement, Employee, Invoice, Lead, Supplier, Expense, ReorderRule, SupplierInvoice, Currency

db = TenantDatabase.objects.get(name='adata')
alias = add_tenant_database(db)
with TenantDatabaseContext(alias):
    c = Company.objects.using(alias).first()
    print(f'Company: {c.name if c else "NONE"} (id={c.id if c else "N/A"})')
    print(f'Products:         {Product.objects.using(alias).count()}')
    print(f'Warehouses:       {Warehouse.objects.using(alias).count()}')
    print(f'StockMovements:   {StockMovement.objects.using(alias).count()}')
    print(f'ReorderRules:     {ReorderRule.objects.using(alias).count()}')
    print(f'Employees:        {Employee.objects.using(alias).count()}')
    print(f'Invoices:         {Invoice.objects.using(alias).count()}')
    print(f'Leads:            {Lead.objects.using(alias).count()}')
    print(f'Suppliers:        {Supplier.objects.using(alias).count()}')
    print(f'SupplierInvoices: {SupplierInvoice.objects.using(alias).count()}')
    print(f'Expenses:         {Expense.objects.using(alias).count()}')
    print(f'Currencies:       {Currency.objects.using(alias).count()}')
