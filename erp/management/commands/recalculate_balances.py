"""
Management command to recalculate all account balances from posted journal entries.

Usage:
    python manage.py recalculate_balances                    # all active tenants
    python manage.py recalculate_balances --tenant <name>    # specific tenant by db name

This resets each account's current_balance to opening_balance + net effect
of all posted journal entry lines, respecting the account's normal balance
direction (debit-normal for assets/expenses, credit-normal for
liabilities/equity/income).
"""

from django.core.management.base import BaseCommand

from erp.models import Account
from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database


class Command(BaseCommand):
    help = "Recalculate current_balance for all accounts from posted journal entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            default=None,
            help="Tenant database name (e.g. erp_pg_alkuraimi). If omitted, all active tenants are processed.",
        )

    def handle(self, *args, **options):
        tenant_name = options["tenant"]

        if tenant_name:
            tenants = TenantDatabase.objects.filter(name=tenant_name, status="active")
            if not tenants.exists():
                self.stderr.write(self.style.ERROR(f"No active tenant found with name '{tenant_name}'."))
                all_tenants = TenantDatabase.objects.filter(status="active").values_list("name", flat=True)
                if all_tenants:
                    self.stderr.write(f"Available: {', '.join(all_tenants)}")
                return
        else:
            tenants = TenantDatabase.objects.filter(status="active")

        if not tenants.exists():
            self.stdout.write(self.style.WARNING("No active tenant databases found."))
            return

        for tenant_db in tenants:
            db_alias = add_tenant_database(tenant_db)
            self.stdout.write(f"\n--- Recalculating [{tenant_db.name}] ---")
            self._recalculate_for_db(db_alias, tenant_db.name)

    def _recalculate_for_db(self, db_alias, db_name):
        accounts = Account.objects.using(db_alias).all()
        count = 0
        changed = 0

        for account in accounts:
            old_balance = account.current_balance
            account.recalculate_balance(db_alias=db_alias)
            account.save(using=db_alias, update_fields=["current_balance"])
            if old_balance != account.current_balance:
                self.stdout.write(f"  {account.code} {account.name}: {old_balance} → {account.current_balance}")
                changed += 1
            count += 1

        self.stdout.write(self.style.SUCCESS(f"[{db_name}] {count} accounts processed, {changed} balances updated."))
