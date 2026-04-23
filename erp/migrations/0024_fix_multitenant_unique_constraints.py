"""
Migration: fix multi-tenant unique constraint violations.

Several models had globally unique fields (unique=True) that should
only be unique within a company.  This migration:

  1. Drops the global unique index on each affected field.
  2. Adds a (company, <field>) unique_together constraint instead.

Models fixed:
  - Employee.employee_id
  - Supplier.supplier_id
  - PurchaseOrder.po_number
  - SupplierPayment.payment_number
  - Lead.lead_number
  - POSOrder.order_number
  - ServicePricing.code
  - ServicePackage.code
  - Quote.quote_number
  - Product.sku  (index renamed to idx_prod_sku covering (company, sku))
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0023_fix_customer_id_unique_per_company"),
    ]

    operations = [
        # ── Employee ──────────────────────────────────────────────────────
        migrations.AlterField(
            model_name="employee",
            name="employee_id",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name="employee",
            unique_together={("company", "employee_id")},
        ),
        # ── Supplier ──────────────────────────────────────────────────────
        migrations.AlterField(
            model_name="supplier",
            name="supplier_id",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name="supplier",
            unique_together={("company", "supplier_id")},
        ),
        # ── PurchaseOrder ─────────────────────────────────────────────────
        migrations.AlterField(
            model_name="purchaseorder",
            name="po_number",
            field=models.CharField(max_length=50),
        ),
        migrations.AlterUniqueTogether(
            name="purchaseorder",
            unique_together={("company", "po_number")},
        ),
        # ── SupplierPayment ───────────────────────────────────────────────
        migrations.AlterField(
            model_name="supplierpayment",
            name="payment_number",
            field=models.CharField(max_length=50),
        ),
        migrations.AlterUniqueTogether(
            name="supplierpayment",
            unique_together={("company", "payment_number")},
        ),
        # ── Lead ──────────────────────────────────────────────────────────
        migrations.AlterField(
            model_name="lead",
            name="lead_number",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name="lead",
            unique_together={("company", "lead_number")},
        ),
        # ── POSOrder ──────────────────────────────────────────────────────
        migrations.AlterField(
            model_name="posorder",
            name="order_number",
            field=models.CharField(max_length=50),
        ),
        migrations.AlterUniqueTogether(
            name="posorder",
            unique_together={("company", "order_number")},
        ),
        # ── ServicePricing ────────────────────────────────────────────────
        migrations.AlterField(
            model_name="servicepricing",
            name="code",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name="servicepricing",
            unique_together={("company", "code")},
        ),
        # ── ServicePackage ────────────────────────────────────────────────
        migrations.AlterField(
            model_name="servicepackage",
            name="code",
            field=models.CharField(max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name="servicepackage",
            unique_together={("company", "code")},
        ),
        # ── Quote ─────────────────────────────────────────────────────────
        migrations.AlterField(
            model_name="quote",
            name="quote_number",
            field=models.CharField(max_length=50),
        ),
        migrations.AlterUniqueTogether(
            name="quote",
            unique_together={("company", "quote_number")},
        ),
        # ── Product ───────────────────────────────────────────────────────
        # Rename the old global SKU index to the new (company, sku) index.
        migrations.RemoveIndex(
            model_name="product",
            name="idx_prod_sku",
        ),
        migrations.AlterField(
            model_name="product",
            name="sku",
            field=models.CharField(max_length=50, verbose_name="SKU"),
        ),
        migrations.AlterUniqueTogether(
            name="product",
            unique_together={("company", "sku")},
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["company", "sku"], name="idx_prod_sku"),
        ),
    ]
