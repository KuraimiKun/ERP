"""
Test Helpers & Base Test Case

Provides a reusable ERPTestCase base that sets up a complete shared
fixture (currency, company, department, accounts, employee, customer,
supplier, etc.) so every downstream test module can focus on the logic
under test rather than repeating boilerplate data creation.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

from erp.models import (
    Currency, Company, Department, Branch, FiscalYear, Sequence,
    Account, TaxRate, PaymentMethod,
    Customer, Invoice, InvoiceLine, Payment, PaymentAllocation,
    Expense, ExpenseCategory, JournalEntry, JournalEntryLine,
    Employee, LeaveType, LeaveRequest, Attendance, Payroll,
    Supplier,
    Lead, Campaign, Task,
    ServiceCategory, ServicePricing, ProductCategory, Product,
    Warehouse, WarehouseZone, WarehouseBin,
    POSTerminal,
)

User = get_user_model()


class ERPTestCase(TestCase):
    """
    Base test case that bootstraps a minimal but realistic ERP dataset.

    Subclass this instead of ``django.test.TestCase`` whenever your test
    needs models that reference Company, Currency, User, etc.
    """

    @classmethod
    def setUpTestData(cls):
        # ── Auth user ──
        cls.user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User',
        )
        cls.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
        )

        # ── Currency ──
        cls.currency = Currency.objects.create(
            code='SAR', name='Saudi Riyal', symbol='﷼',
            exchange_rate=1, is_base=True, decimal_places=2,
        )
        cls.usd = Currency.objects.create(
            code='USD', name='US Dollar', symbol='$',
            exchange_rate=Decimal('3.75'), is_base=False,
        )

        # ── Company ──
        cls.company = Company.objects.create(
            name='Test Corp',
            email='company@test.com',
            phone='+966500000000',
            address='123 Test St',
            city='Riyadh',
            country='Saudi Arabia',
            base_currency=cls.currency,
            created_by=cls.user,
        )

        # ── Department ──
        cls.department = Department.objects.create(
            company=cls.company,
            name='Engineering',
            code='ENG',
            is_active=True,
            created_by=cls.user,
        )

        # ── Branch ──
        cls.branch = Branch.objects.create(
            company=cls.company,
            name='HQ',
            address='HQ Address',
            city='Riyadh',
            country='Saudi Arabia',
            is_headquarters=True,
            created_by=cls.user,
        )

        # ── Fiscal Year ──
        cls.fiscal_year = FiscalYear.objects.create(
            company=cls.company,
            name='FY2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
            created_by=cls.user,
        )

        # ── Chart of Accounts ──
        cls.cash_account = Account.objects.create(
            company=cls.company, code='1000', name='Cash',
            account_type='asset', created_by=cls.user,
        )
        cls.ar_account = Account.objects.create(
            company=cls.company, code='1200', name='Accounts Receivable',
            account_type='asset', created_by=cls.user,
        )
        cls.ap_account = Account.objects.create(
            company=cls.company, code='2000', name='Accounts Payable',
            account_type='liability', created_by=cls.user,
        )
        cls.revenue_account = Account.objects.create(
            company=cls.company, code='4000', name='Sales Revenue',
            account_type='income', created_by=cls.user,
        )
        cls.expense_account = Account.objects.create(
            company=cls.company, code='5000', name='Cost of Goods Sold',
            account_type='expense', created_by=cls.user,
        )
        cls.salary_expense_account = Account.objects.create(
            company=cls.company, code='6100', name='Salary Expense',
            account_type='expense', created_by=cls.user,
        )
        cls.salary_payable_account = Account.objects.create(
            company=cls.company, code='2300', name='Salary Payable',
            account_type='liability', created_by=cls.user,
        )

        # ── Tax ──
        cls.tax_rate = TaxRate.objects.create(
            company=cls.company, name='VAT 15%', rate=Decimal('15.00'),
            is_default=True,
        )
        cls.zero_tax = TaxRate.objects.create(
            company=cls.company, name='Zero Rated', rate=Decimal('0'),
        )

        # ── Payment Method ──
        cls.payment_method = PaymentMethod.objects.create(
            company=cls.company, name='Bank Transfer',
            code='BANK', account=cls.cash_account,
        )

        # ── Employee ──
        cls.employee = Employee.objects.create(
            company=cls.company,
            department=cls.department,
            branch=cls.branch,
            employee_id='EMP-0001',
            first_name='Ahmad',
            last_name='Ali',
            gender='male',
            date_of_birth=date(1990, 5, 15),
            nationality='Saudi',
            email='ahmad@company.com',
            phone='+966500000001',
            job_title='Developer',
            hire_date=date(2023, 1, 1),
            basic_salary=Decimal('10000'),
            currency=cls.currency,
            created_by=cls.user,
        )

        # ── Customer ──
        cls.customer = Customer.objects.create(
            company=cls.company,
            customer_id='CUS-0001',
            name='Acme LLC',
            email='acme@test.com',
            phone='+966500000002',
            currency=cls.currency,
            credit_limit=Decimal('50000'),
            payment_terms=30,
            created_by=cls.user,
        )

        # ── Supplier ──
        cls.supplier = Supplier.objects.create(
            company=cls.company,
            supplier_id='SUP-0001',
            supplier_type='other',
            name='Parts Inc',
            email='parts@test.com',
            currency=cls.currency,
            created_by=cls.user,
        )

        # ── Expense Category ──
        cls.expense_category = ExpenseCategory.objects.create(
            company=cls.company, name='Office Supplies',
            account=cls.expense_account,
        )

        # ── Product Category ──
        cls.product_category = ProductCategory.objects.create(
            company=cls.company, name='Electronics',
            code='ELEC',
        )

        # ── Product ──
        cls.product = Product.objects.create(
            company=cls.company,
            sku='PROD-0001',
            name='Widget A',
            product_type='physical',
            category=cls.product_category,
            currency=cls.currency,
            selling_price=Decimal('100'),
            cost_price=Decimal('60'),
            min_selling_price=Decimal('80'),
            track_inventory=True,
            quantity_on_hand=Decimal('50'),
            reorder_level=Decimal('10'),
            reorder_quantity=Decimal('25'),
            created_by=cls.user,
        )

        # ── Warehouse ──
        cls.warehouse = Warehouse.objects.create(
            company=cls.company, code='WH1', name='Main Warehouse',
            created_by=cls.user,
        )
