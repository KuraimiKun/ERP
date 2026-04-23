"""
Test Helpers & Base Test Case

Provides a reusable ERPTestCase base that sets up a complete shared
fixture (currency, company, department, accounts, employee, customer,
supplier, etc.) so every downstream test module can focus on the logic
under test rather than repeating boilerplate data creation.

ERPAPITestCase extends ERPTestCase with DRF APIClient, token auth,
and an employee→user linkage so API permission checks pass.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from erp.models import (
    Currency,
    Company,
    Department,
    Branch,
    FiscalYear,
    Account,
    TaxRate,
    PaymentMethod,
    Customer,
    ExpenseCategory,
    Employee,
    Supplier,
    ProductCategory,
    Product,
    Warehouse,
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
            email="test@example.com",
            password="TestPass123!",
            first_name="Test",
            last_name="User",
        )
        cls.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPass123!",
            first_name="Admin",
            last_name="User",
        )

        # ── Currency ──
        cls.currency = Currency.objects.create(
            code="SAR",
            name="Saudi Riyal",
            symbol="﷼",
            exchange_rate=1,
            is_base=True,
            decimal_places=2,
        )
        cls.usd = Currency.objects.create(
            code="USD",
            name="US Dollar",
            symbol="$",
            exchange_rate=Decimal("3.75"),
            is_base=False,
        )

        # ── Company ──
        cls.company = Company.objects.create(
            name="Test Corp",
            email="company@test.com",
            phone="+966500000000",
            address="123 Test St",
            city="Riyadh",
            country="Saudi Arabia",
            base_currency=cls.currency,
            created_by=cls.user,
        )

        # ── Department ──
        cls.department = Department.objects.create(
            company=cls.company,
            name="Engineering",
            code="ENG",
            is_active=True,
            created_by=cls.user,
        )

        # ── Branch ──
        cls.branch = Branch.objects.create(
            company=cls.company,
            name="HQ",
            address="HQ Address",
            city="Riyadh",
            country="Saudi Arabia",
            is_headquarters=True,
            created_by=cls.user,
        )

        # ── Fiscal Year ──
        cls.fiscal_year = FiscalYear.objects.create(
            company=cls.company,
            name="FY2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
            created_by=cls.user,
        )

        # ── Chart of Accounts ──
        cls.cash_account = Account.objects.create(
            company=cls.company,
            code="1000",
            name="Cash",
            account_type="asset",
            created_by=cls.user,
        )
        cls.ar_account = Account.objects.create(
            company=cls.company,
            code="1200",
            name="Accounts Receivable",
            account_type="asset",
            created_by=cls.user,
        )
        cls.ap_account = Account.objects.create(
            company=cls.company,
            code="2000",
            name="Accounts Payable",
            account_type="liability",
            created_by=cls.user,
        )
        cls.revenue_account = Account.objects.create(
            company=cls.company,
            code="4000",
            name="Sales Revenue",
            account_type="income",
            created_by=cls.user,
        )
        cls.expense_account = Account.objects.create(
            company=cls.company,
            code="5000",
            name="Cost of Goods Sold",
            account_type="expense",
            created_by=cls.user,
        )
        cls.salary_expense_account = Account.objects.create(
            company=cls.company,
            code="6100",
            name="Salary Expense",
            account_type="expense",
            created_by=cls.user,
        )
        cls.salary_payable_account = Account.objects.create(
            company=cls.company,
            code="2300",
            name="Salary Payable",
            account_type="liability",
            created_by=cls.user,
        )

        # ── Tax ──
        cls.tax_rate = TaxRate.objects.create(
            company=cls.company,
            name="VAT 15%",
            rate=Decimal("15.00"),
            is_default=True,
        )
        cls.zero_tax = TaxRate.objects.create(
            company=cls.company,
            name="Zero Rated",
            rate=Decimal("0"),
        )

        # ── Payment Method ──
        cls.payment_method = PaymentMethod.objects.create(
            company=cls.company,
            name="Bank Transfer",
            code="BANK",
            account=cls.cash_account,
        )

        # ── Employee ──
        cls.employee = Employee.objects.create(
            company=cls.company,
            department=cls.department,
            branch=cls.branch,
            employee_id="EMP-0001",
            first_name="Ahmad",
            last_name="Ali",
            gender="male",
            date_of_birth=date(1990, 5, 15),
            nationality="Saudi",
            email="ahmad@company.com",
            phone="+966500000001",
            job_title="Developer",
            hire_date=date(2023, 1, 1),
            basic_salary=Decimal("10000"),
            currency=cls.currency,
            created_by=cls.user,
        )

        # ── Customer ──
        cls.customer = Customer.objects.create(
            company=cls.company,
            customer_id="CUS-0001",
            name="Acme LLC",
            email="acme@test.com",
            phone="+966500000002",
            currency=cls.currency,
            credit_limit=Decimal("50000"),
            payment_terms=30,
            created_by=cls.user,
        )

        # ── Supplier ──
        cls.supplier = Supplier.objects.create(
            company=cls.company,
            supplier_id="SUP-0001",
            supplier_type="other",
            name="Parts Inc",
            email="parts@test.com",
            currency=cls.currency,
            created_by=cls.user,
        )

        # ── Expense Category ──
        cls.expense_category = ExpenseCategory.objects.create(
            company=cls.company,
            name="Office Supplies",
            account=cls.expense_account,
        )

        # ── Product Category ──
        cls.product_category = ProductCategory.objects.create(
            company=cls.company,
            name="Electronics",
            code="ELEC",
        )

        # ── Product ──
        cls.product = Product.objects.create(
            company=cls.company,
            sku="PROD-0001",
            name="Widget A",
            product_type="physical",
            category=cls.product_category,
            currency=cls.currency,
            selling_price=Decimal("100"),
            cost_price=Decimal("60"),
            min_selling_price=Decimal("80"),
            track_inventory=True,
            quantity_on_hand=Decimal("50"),
            reorder_level=Decimal("10"),
            reorder_quantity=Decimal("25"),
            created_by=cls.user,
        )

        # ── Warehouse ──
        cls.warehouse = Warehouse.objects.create(
            company=cls.company,
            code="WH1",
            name="Main Warehouse",
            created_by=cls.user,
        )


class ERPAPITestCase(ERPTestCase):
    """
    Base test case for API tests with DRF client and token auth.

    Links the default employee to the test user so that
    ``ERPBaseViewSet.get_company()`` (which traverses
    ``request.user.employee_profile.company``) works correctly.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Link employee to user – required by IsCompanyUser permission
        cls.employee.user = cls.user
        cls.employee.save()
        # Auth tokens
        cls.token = Token.objects.create(user=cls.user)
        cls.admin_token = Token.objects.create(user=cls.admin_user)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def get_admin_client(self):
        """Return an APIClient authenticated as the admin/superuser."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        return client

    @classmethod
    def create_other_company_user(cls):
        """Create a user belonging to a different company for isolation tests."""
        other_user = User.objects.create_user(
            email="other@example.com",
            password="OtherPass123!",
        )
        other_company = Company.objects.create(
            name="Other Corp",
            email="other@corp.com",
            phone="+966500000099",
            base_currency=cls.currency,
            created_by=other_user,
        )
        other_dept = Department.objects.create(
            company=other_company,
            name="Ops",
            code="OPS",
            is_active=True,
            created_by=other_user,
        )
        other_employee = Employee.objects.create(
            company=other_company,
            department=other_dept,
            employee_id="EMP-9999",
            first_name="Other",
            last_name="User",
            gender="male",
            date_of_birth=date(1992, 1, 1),
            nationality="Saudi",
            email="other@corp.com",
            phone="+966500000099",
            job_title="Manager",
            hire_date=date(2024, 1, 1),
            basic_salary=Decimal("8000"),
            currency=cls.currency,
            user=other_user,
            created_by=other_user,
        )
        other_token = Token.objects.create(user=other_user)
        return other_user, other_company, other_employee, other_token
