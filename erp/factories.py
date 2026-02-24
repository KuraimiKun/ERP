"""
Factory Boy factories for ERP model test data generation.

Usage (from tests or seed_tenant command):
    from erp.factories import CustomerFactory, ProductFactory
    customers = CustomerFactory.create_batch(50, company=company, currency=currency)
"""

import uuid
import random
from datetime import timedelta
from decimal import Decimal

import factory
from factory import LazyFunction, LazyAttribute, SubFactory, Faker
from factory.django import DjangoModelFactory
from django.utils import timezone

from erp.models import (
    Currency,
    Company,
    Department,
    TaxRate,
    PaymentMethod,
    Account,
    Customer,
    Supplier,
    Employee,
    ExpenseCategory,
    ServiceCategory,
    ServicePricing,
    ProductCategory,
    Product,
    Lead,
    Campaign,
    Task,
)


def _uuid_id(prefix: str, length: int = 8) -> str:
    """Generate a compact unique ID with a prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:length].upper()}"


# ─── Master / Reference Data Factories ────────────────────────────────────────

class DepartmentFactory(DjangoModelFactory):
    """Company department. Pass company=<Company> when calling."""

    class Meta:
        model = Department

    name = Faker("job")
    name_ar = LazyAttribute(lambda o: f"قسم {o.name[:20]}")
    code = LazyFunction(lambda: uuid.uuid4().hex[:4].upper())
    is_active = True


class TaxRateFactory(DjangoModelFactory):
    """Tax rate entry."""

    class Meta:
        model = TaxRate
        django_get_or_create = ("company", "name")

    name = LazyFunction(lambda: random.choice(["VAT 15%", "VAT 5%", "Zero Rated", "Exempt"]))
    name_ar = LazyAttribute(lambda o: f"ضريبة {o.name[:20]}")
    rate = LazyFunction(lambda: Decimal(random.choice(["0.00", "5.00", "15.00"])))
    is_default = False
    is_active = True


class ExpenseCategoryFactory(DjangoModelFactory):
    """Expense category."""

    class Meta:
        model = ExpenseCategory
        django_get_or_create = ("company", "name")

    name = LazyFunction(
        lambda: random.choice(
            ["Travel", "Office Supplies", "Software", "Marketing", "Utilities", "Meals", "Training"]
        )
    )
    name_ar = LazyAttribute(lambda o: f"مصروف {o.name[:15]}")
    is_active = True


class ServiceCategoryFactory(DjangoModelFactory):
    """Service category."""

    class Meta:
        model = ServiceCategory

    name = LazyFunction(
        lambda: random.choice(
            ["Consulting", "Design", "Development", "Support", "Training", "Logistics", "Tourism"]
        )
        + f" {uuid.uuid4().hex[:4].upper()}"
    )
    name_ar = LazyAttribute(lambda o: f"خدمات {o.name[:20]}")
    code = LazyFunction(lambda: uuid.uuid4().hex[:4].upper())
    is_active = True


class ProductCategoryFactory(DjangoModelFactory):
    """Product category."""

    class Meta:
        model = ProductCategory

    name = LazyFunction(
        lambda: random.choice(
            ["Electronics", "Furniture", "Stationery", "Raw Materials", "Finished Goods", "Packaging"]
        )
        + f" {uuid.uuid4().hex[:4].upper()}"
    )
    name_ar = LazyAttribute(lambda o: f"تصنيف {o.name[:20]}")
    code = LazyFunction(lambda: uuid.uuid4().hex[:4].upper())
    is_active = True


class CustomerFactory(DjangoModelFactory):
    """Customer record."""

    class Meta:
        model = Customer

    customer_id = LazyFunction(lambda: _uuid_id("C"))
    customer_type = LazyFunction(
        lambda: random.choice(["individual", "company", "government"])
    )
    name = Faker("company")
    name_ar = LazyAttribute(lambda o: f"شركة {o.name[:30]}")
    email = LazyFunction(lambda: f"{uuid.uuid4().hex[:8]}@example.com")
    phone = LazyFunction(lambda: f"+966{random.randint(500000000, 599999999)}")
    billing_city = Faker("city")
    billing_country = LazyFunction(
        lambda: random.choice(["Saudi Arabia", "UAE", "Kuwait", "Egypt", "Jordan"])
    )
    credit_limit = LazyFunction(lambda: Decimal(random.choice(["10000", "25000", "50000", "100000"])))
    payment_terms = LazyFunction(lambda: random.choice([0, 15, 30, 45, 60]))
    is_active = True


class SupplierFactory(DjangoModelFactory):
    """Supplier / vendor record."""

    class Meta:
        model = Supplier

    supplier_id = LazyFunction(lambda: _uuid_id("S"))
    supplier_type = LazyFunction(
        lambda: random.choice(
            ["airline", "hotel", "transport", "tour_operator", "other"]
        )
    )
    name = Faker("company")
    name_ar = LazyAttribute(lambda o: f"مورد {o.name[:30]}")
    email = LazyFunction(lambda: f"{uuid.uuid4().hex[:8]}@supplier.com")
    phone = LazyFunction(lambda: f"+966{random.randint(500000000, 599999999)}")
    city = Faker("city")
    country = LazyFunction(
        lambda: random.choice(["Saudi Arabia", "UAE", "Turkey", "Germany", "USA"])
    )
    payment_terms = LazyFunction(lambda: random.choice([30, 45, 60, 90]))
    is_active = True


class EmployeeFactory(DjangoModelFactory):
    """Employee record."""

    class Meta:
        model = Employee

    employee_id = LazyFunction(lambda: _uuid_id("EMP", 6))
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    gender = LazyFunction(lambda: random.choice(["male", "female"]))
    date_of_birth = Faker("date_of_birth", minimum_age=22, maximum_age=55)
    nationality = LazyFunction(
        lambda: random.choice(
            ["Saudi", "Emirati", "Egyptian", "Jordanian", "Lebanese", "Indian", "Filipino"]
        )
    )
    email = LazyFunction(lambda: f"{uuid.uuid4().hex[:8]}@company.com")
    phone = LazyFunction(lambda: f"+966{random.randint(500000000, 599999999)}")
    job_title = Faker("job")
    employment_type = LazyFunction(
        lambda: random.choice(["full_time", "part_time", "contract"])
    )
    employment_status = "active"
    hire_date = Faker("date_between", start_date="-5y", end_date="-30d")
    basic_salary = LazyFunction(
        lambda: Decimal(str(random.randint(3000, 25000)))
    )
    annual_leave_balance = LazyFunction(lambda: Decimal(str(random.randint(0, 30))))


class ServicePricingFactory(DjangoModelFactory):
    """Service pricing entry."""

    class Meta:
        model = ServicePricing

    code = LazyFunction(lambda: _uuid_id("SVC", 6))
    name = Faker("catch_phrase")
    name_ar = LazyAttribute(lambda o: f"خدمة {o.name[:30]}")
    pricing_type = LazyFunction(
        lambda: random.choice(["fixed", "tiered", "variable"])
    )
    base_price = LazyFunction(lambda: Decimal(str(random.randint(100, 5000))))
    cost_price = LazyFunction(lambda: Decimal(str(random.randint(50, 2000))))
    is_active = True


class ProductFactory(DjangoModelFactory):
    """Product / inventory item."""

    class Meta:
        model = Product

    sku = LazyFunction(lambda: _uuid_id("SKU", 8))
    name = Faker("catch_phrase")
    name_ar = LazyAttribute(lambda o: f"منتج {o.name[:30]}")
    product_type = LazyFunction(
        lambda: random.choice(["physical", "digital", "consumable"])
    )
    selling_price = LazyFunction(lambda: Decimal(str(random.randint(10, 1000))))
    cost_price = LazyFunction(lambda: Decimal(str(random.randint(5, 500))))
    min_selling_price = LazyAttribute(lambda o: o.cost_price * Decimal("1.05"))
    track_inventory = True
    quantity_on_hand = LazyFunction(lambda: Decimal(str(random.randint(0, 500))))
    reorder_level = LazyFunction(lambda: Decimal(str(random.randint(5, 50))))
    reorder_quantity = LazyFunction(lambda: Decimal(str(random.randint(10, 100))))
    unit_of_measure = LazyFunction(lambda: random.choice(["unit", "kg", "m", "litre", "box"]))
    is_active = True


class LeadFactory(DjangoModelFactory):
    """Sales lead / prospect."""

    class Meta:
        model = Lead

    lead_number = LazyFunction(lambda: _uuid_id("LEAD", 6))
    status = LazyFunction(
        lambda: random.choice(
            ["new", "contacted", "qualified", "proposal", "negotiation", "won", "lost"]
        )
    )
    source = LazyFunction(
        lambda: random.choice(
            ["website", "referral", "social", "advertisement", "cold_call", "walk_in"]
        )
    )
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    email = LazyFunction(lambda: f"{uuid.uuid4().hex[:8]}@prospect.com")
    phone = LazyFunction(lambda: f"+966{random.randint(500000000, 599999999)}")
    city = Faker("city")
    country = LazyFunction(
        lambda: random.choice(["Saudi Arabia", "UAE", "Kuwait", "Egypt", "Jordan"])
    )
    estimated_value = LazyFunction(
        lambda: Decimal(str(random.randint(1000, 100000)))
    )
    probability = LazyFunction(lambda: random.randint(10, 90))
    notes = Faker("paragraph", nb_sentences=2)


class CampaignFactory(DjangoModelFactory):
    """Marketing campaign."""

    class Meta:
        model = Campaign

    name = Faker("catch_phrase")
    campaign_type = LazyFunction(
        lambda: random.choice(["email", "sms", "social", "ads", "event", "referral", "other"])
    )
    description = Faker("paragraph", nb_sentences=3)
    status = LazyFunction(
        lambda: random.choice(["draft", "active", "paused", "completed"])
    )
    start_date = Faker("date_between", start_date="-1y", end_date="-30d")
    end_date = Faker("date_between", start_date="-29d", end_date="+6m")
    budget = LazyFunction(lambda: Decimal(str(random.randint(5000, 50000))))


class TaskFactory(DjangoModelFactory):
    """Task / to-do item."""

    class Meta:
        model = Task

    title = Faker("sentence", nb_words=5)
    description = Faker("paragraph", nb_sentences=2)
    status = LazyFunction(
        lambda: random.choice(["todo", "in_progress", "on_hold", "completed", "cancelled"])
    )
    priority = LazyFunction(
        lambda: random.choice(["low", "medium", "high", "urgent"])
    )
    due_date = LazyFunction(
        lambda: timezone.now() + timedelta(days=random.randint(-30, 60))
    )
