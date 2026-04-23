"""
Report Builder — Data Source Registry

Defines the allowlisted data sources, fields, operators, and aggregates
available to the dynamic report builder. This is the **security boundary**:
users can only query fields explicitly listed here.

Every data source maps to a Django model and declares:
  - fields: dict of field_key → {type, label, choices?}
  - select_related / prefetch_related for efficient queries
  - company_field: the ORM path to tenant-isolate the queryset
"""

from erp.models import (
    Customer,
    Invoice,
    Payment,
    Expense,
    Employee,
    Attendance,
    Payroll,
    Supplier,
    PurchaseOrder,
    Lead,
    Account,
    JournalEntry,
    Quote,
)

# ── Field-type constants ────────────────────────────────────────────────────

TYPE_STRING = "string"
TYPE_DECIMAL = "decimal"
TYPE_INTEGER = "integer"
TYPE_DATE = "date"
TYPE_DATETIME = "datetime"
TYPE_BOOLEAN = "boolean"
TYPE_CHOICE = "choice"

# ── Operators allowed per field type ────────────────────────────────────────

OPERATORS_BY_TYPE = {
    TYPE_STRING: ["eq", "neq", "contains", "startswith", "isnull"],
    TYPE_DECIMAL: ["eq", "neq", "gt", "gte", "lt", "lte", "range", "isnull"],
    TYPE_INTEGER: ["eq", "neq", "gt", "gte", "lt", "lte", "range", "isnull"],
    TYPE_DATE: ["eq", "neq", "gt", "gte", "lt", "lte", "range", "isnull"],
    TYPE_DATETIME: ["eq", "neq", "gt", "gte", "lt", "lte", "range", "isnull"],
    TYPE_BOOLEAN: ["eq"],
    TYPE_CHOICE: ["eq", "neq", "in"],
}

AGGREGATE_FUNCTIONS = ["sum", "count", "avg", "min", "max"]

# Hard row limit (can be overridden in SystemSetting per-company)
MAX_REPORT_ROWS = 10_000

# ── Data source registry ───────────────────────────────────────────────────

REPORT_DATA_SOURCES = {
    # ── Sales & Customers ───────────────────────────────────────────────
    "customer": {
        "model": Customer,
        "label": "Customers",
        "icon": "bi-people",
        "company_field": "company",
        "select_related": ["currency"],
        "fields": {
            "customer_id": {"type": TYPE_STRING, "label": "Customer ID"},
            "name": {"type": TYPE_STRING, "label": "Name"},
            "customer_type": {
                "type": TYPE_CHOICE,
                "label": "Type",
                "choices": [("individual", "Individual"), ("company", "Company"), ("government", "Government")],
            },
            "email": {"type": TYPE_STRING, "label": "Email"},
            "phone": {"type": TYPE_STRING, "label": "Phone"},
            "billing_city": {"type": TYPE_STRING, "label": "City"},
            "billing_country": {"type": TYPE_STRING, "label": "Country"},
            "credit_limit": {"type": TYPE_DECIMAL, "label": "Credit Limit"},
            "current_balance": {"type": TYPE_DECIMAL, "label": "Current Balance"},
            "payment_terms": {"type": TYPE_INTEGER, "label": "Payment Terms (days)"},
            "currency__code": {"type": TYPE_STRING, "label": "Currency"},
            "is_active": {"type": TYPE_BOOLEAN, "label": "Active"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    "invoice": {
        "model": Invoice,
        "label": "Invoices",
        "icon": "bi-receipt",
        "company_field": "company",
        "select_related": ["customer", "currency"],
        "fields": {
            "invoice_number": {"type": TYPE_STRING, "label": "Invoice #"},
            "invoice_type": {
                "type": TYPE_CHOICE,
                "label": "Type",
                "choices": [
                    ("standard", "Standard"),
                    ("credit", "Credit Note"),
                    ("debit", "Debit Note"),
                    ("proforma", "Proforma"),
                ],
            },
            "customer__name": {"type": TYPE_STRING, "label": "Customer"},
            "customer__customer_id": {"type": TYPE_STRING, "label": "Customer ID"},
            "invoice_date": {"type": TYPE_DATE, "label": "Invoice Date"},
            "due_date": {"type": TYPE_DATE, "label": "Due Date"},
            "subtotal": {"type": TYPE_DECIMAL, "label": "Subtotal"},
            "discount_amount": {"type": TYPE_DECIMAL, "label": "Discount"},
            "tax_amount": {"type": TYPE_DECIMAL, "label": "Tax"},
            "total_amount": {"type": TYPE_DECIMAL, "label": "Total"},
            "paid_amount": {"type": TYPE_DECIMAL, "label": "Paid"},
            "balance_due": {"type": TYPE_DECIMAL, "label": "Balance Due"},
            "status": {
                "type": TYPE_CHOICE,
                "label": "Status",
                "choices": [
                    ("draft", "Draft"),
                    ("sent", "Sent"),
                    ("partial", "Partial"),
                    ("paid", "Paid"),
                    ("overdue", "Overdue"),
                    ("cancelled", "Cancelled"),
                ],
            },
            "currency__code": {"type": TYPE_STRING, "label": "Currency"},
            "reference": {"type": TYPE_STRING, "label": "Reference"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    "payment": {
        "model": Payment,
        "label": "Payments",
        "icon": "bi-cash-coin",
        "company_field": "company",
        "select_related": ["customer", "payment_method", "currency"],
        "fields": {
            "payment_number": {"type": TYPE_STRING, "label": "Payment #"},
            "customer__name": {"type": TYPE_STRING, "label": "Customer"},
            "payment_type": {
                "type": TYPE_CHOICE,
                "label": "Type",
                "choices": [("received", "Received"), ("refund", "Refund")],
            },
            "payment_date": {"type": TYPE_DATE, "label": "Payment Date"},
            "payment_method__name": {"type": TYPE_STRING, "label": "Payment Method"},
            "amount": {"type": TYPE_DECIMAL, "label": "Amount"},
            "allocated_amount": {"type": TYPE_DECIMAL, "label": "Allocated"},
            "unallocated_amount": {"type": TYPE_DECIMAL, "label": "Unallocated"},
            "currency__code": {"type": TYPE_STRING, "label": "Currency"},
            "reference_number": {"type": TYPE_STRING, "label": "Reference"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    "expense": {
        "model": Expense,
        "label": "Expenses",
        "icon": "bi-wallet2",
        "company_field": "company",
        "select_related": ["category", "employee", "currency", "supplier"],
        "fields": {
            "expense_number": {"type": TYPE_STRING, "label": "Expense #"},
            "expense_date": {"type": TYPE_DATE, "label": "Date"},
            "category__name": {"type": TYPE_STRING, "label": "Category"},
            "supplier__name": {"type": TYPE_STRING, "label": "Supplier"},
            "description": {"type": TYPE_STRING, "label": "Description"},
            "amount": {"type": TYPE_DECIMAL, "label": "Amount"},
            "tax_amount": {"type": TYPE_DECIMAL, "label": "Tax"},
            "total_amount": {"type": TYPE_DECIMAL, "label": "Total"},
            "status": {
                "type": TYPE_CHOICE,
                "label": "Status",
                "choices": [
                    ("draft", "Draft"),
                    ("submitted", "Submitted"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("paid", "Paid"),
                ],
            },
            "currency__code": {"type": TYPE_STRING, "label": "Currency"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    # ── Purchases ───────────────────────────────────────────────────────
    "supplier": {
        "model": Supplier,
        "label": "Suppliers",
        "icon": "bi-truck",
        "company_field": "company",
        "select_related": ["currency"],
        "fields": {
            "supplier_id": {"type": TYPE_STRING, "label": "Supplier ID"},
            "name": {"type": TYPE_STRING, "label": "Name"},
            "supplier_type": {
                "type": TYPE_CHOICE,
                "label": "Type",
                "choices": [("individual", "Individual"), ("company", "Company"), ("government", "Government")],
            },
            "email": {"type": TYPE_STRING, "label": "Email"},
            "phone": {"type": TYPE_STRING, "label": "Phone"},
            "contact_person": {"type": TYPE_STRING, "label": "Contact Person"},
            "city": {"type": TYPE_STRING, "label": "City"},
            "country": {"type": TYPE_STRING, "label": "Country"},
            "current_balance": {"type": TYPE_DECIMAL, "label": "Balance"},
            "currency__code": {"type": TYPE_STRING, "label": "Currency"},
            "is_active": {"type": TYPE_BOOLEAN, "label": "Active"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    "purchase_order": {
        "model": PurchaseOrder,
        "label": "Purchase Orders",
        "icon": "bi-cart-check",
        "company_field": "company",
        "select_related": ["supplier", "currency"],
        "fields": {
            "po_number": {"type": TYPE_STRING, "label": "PO #"},
            "supplier__name": {"type": TYPE_STRING, "label": "Supplier"},
            "order_date": {"type": TYPE_DATE, "label": "Order Date"},
            "expected_date": {"type": TYPE_DATE, "label": "Expected Date"},
            "subtotal": {"type": TYPE_DECIMAL, "label": "Subtotal"},
            "tax_amount": {"type": TYPE_DECIMAL, "label": "Tax"},
            "total_amount": {"type": TYPE_DECIMAL, "label": "Total"},
            "status": {
                "type": TYPE_CHOICE,
                "label": "Status",
                "choices": [
                    ("draft", "Draft"),
                    ("sent", "Sent"),
                    ("confirmed", "Confirmed"),
                    ("received", "Received"),
                    ("cancelled", "Cancelled"),
                ],
            },
            "currency__code": {"type": TYPE_STRING, "label": "Currency"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    # ── Human Resources ─────────────────────────────────────────────────
    "employee": {
        "model": Employee,
        "label": "Employees",
        "icon": "bi-person-badge",
        "company_field": "company",
        "select_related": ["department", "currency"],
        "fields": {
            "employee_id": {"type": TYPE_STRING, "label": "Employee ID"},
            "first_name": {"type": TYPE_STRING, "label": "First Name"},
            "last_name": {"type": TYPE_STRING, "label": "Last Name"},
            "email": {"type": TYPE_STRING, "label": "Email"},
            "phone": {"type": TYPE_STRING, "label": "Phone"},
            "department__name": {"type": TYPE_STRING, "label": "Department"},
            "job_title": {"type": TYPE_STRING, "label": "Job Title"},
            "employment_type": {
                "type": TYPE_CHOICE,
                "label": "Employment Type",
                "choices": [
                    ("full_time", "Full Time"),
                    ("part_time", "Part Time"),
                    ("contract", "Contract"),
                    ("intern", "Intern"),
                ],
            },
            "employment_status": {
                "type": TYPE_CHOICE,
                "label": "Status",
                "choices": [
                    ("active", "Active"),
                    ("on_leave", "On Leave"),
                    ("suspended", "Suspended"),
                    ("terminated", "Terminated"),
                ],
            },
            "hire_date": {"type": TYPE_DATE, "label": "Hire Date"},
            "basic_salary": {"type": TYPE_DECIMAL, "label": "Basic Salary"},
            "currency__code": {"type": TYPE_STRING, "label": "Currency"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    "attendance": {
        "model": Attendance,
        "label": "Attendance",
        "icon": "bi-clock-history",
        "company_field": "employee__company",
        "select_related": ["employee", "employee__department"],
        "fields": {
            "employee__employee_id": {"type": TYPE_STRING, "label": "Employee ID"},
            "employee__first_name": {"type": TYPE_STRING, "label": "First Name"},
            "employee__last_name": {"type": TYPE_STRING, "label": "Last Name"},
            "employee__department__name": {"type": TYPE_STRING, "label": "Department"},
            "date": {"type": TYPE_DATE, "label": "Date"},
            "check_in": {"type": TYPE_DATETIME, "label": "Check In"},
            "check_out": {"type": TYPE_DATETIME, "label": "Check Out"},
            "hours_worked": {"type": TYPE_DECIMAL, "label": "Hours Worked"},
            "overtime_hours": {"type": TYPE_DECIMAL, "label": "Overtime"},
            "is_present": {"type": TYPE_BOOLEAN, "label": "Present"},
            "is_late": {"type": TYPE_BOOLEAN, "label": "Late"},
            "late_minutes": {"type": TYPE_INTEGER, "label": "Late Minutes"},
        },
    },
    "payroll": {
        "model": Payroll,
        "label": "Payroll",
        "icon": "bi-cash-coin",
        "company_field": "employee__company",
        "select_related": ["employee", "employee__department", "currency"],
        "fields": {
            "employee__employee_id": {"type": TYPE_STRING, "label": "Employee ID"},
            "employee__first_name": {"type": TYPE_STRING, "label": "First Name"},
            "employee__last_name": {"type": TYPE_STRING, "label": "Last Name"},
            "employee__department__name": {"type": TYPE_STRING, "label": "Department"},
            "period_start": {"type": TYPE_DATE, "label": "Period Start"},
            "period_end": {"type": TYPE_DATE, "label": "Period End"},
            "basic_salary": {"type": TYPE_DECIMAL, "label": "Basic Salary"},
            "gross_salary": {"type": TYPE_DECIMAL, "label": "Gross Salary"},
            "total_deductions": {"type": TYPE_DECIMAL, "label": "Deductions"},
            "net_salary": {"type": TYPE_DECIMAL, "label": "Net Salary"},
            "status": {
                "type": TYPE_CHOICE,
                "label": "Status",
                "choices": [("draft", "Draft"), ("approved", "Approved"), ("paid", "Paid"), ("cancelled", "Cancelled")],
            },
            "payment_date": {"type": TYPE_DATE, "label": "Payment Date"},
            "currency__code": {"type": TYPE_STRING, "label": "Currency"},
        },
    },
    # ── CRM ─────────────────────────────────────────────────────────────
    "lead": {
        "model": Lead,
        "label": "Leads",
        "icon": "bi-funnel",
        "company_field": "company",
        "select_related": ["assigned_to"],
        "fields": {
            "lead_number": {"type": TYPE_STRING, "label": "Lead #"},
            "first_name": {"type": TYPE_STRING, "label": "First Name"},
            "last_name": {"type": TYPE_STRING, "label": "Last Name"},
            "email": {"type": TYPE_STRING, "label": "Email"},
            "phone": {"type": TYPE_STRING, "label": "Phone"},
            "company_name": {"type": TYPE_STRING, "label": "Company"},
            "source": {
                "type": TYPE_CHOICE,
                "label": "Source",
                "choices": [
                    ("website", "Website"),
                    ("referral", "Referral"),
                    ("social", "Social"),
                    ("email", "Email"),
                    ("phone", "Phone"),
                    ("other", "Other"),
                ],
            },
            "status": {
                "type": TYPE_CHOICE,
                "label": "Status",
                "choices": [
                    ("new", "New"),
                    ("contacted", "Contacted"),
                    ("qualified", "Qualified"),
                    ("proposal", "Proposal"),
                    ("won", "Won"),
                    ("lost", "Lost"),
                ],
            },
            "estimated_value": {"type": TYPE_DECIMAL, "label": "Estimated Value"},
            "probability": {"type": TYPE_INTEGER, "label": "Probability (%)"},
            "expected_close_date": {"type": TYPE_DATE, "label": "Expected Close"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    # ── Finance ─────────────────────────────────────────────────────────
    "account": {
        "model": Account,
        "label": "Chart of Accounts",
        "icon": "bi-journal-text",
        "company_field": "company",
        "select_related": ["parent"],
        "fields": {
            "code": {"type": TYPE_STRING, "label": "Code"},
            "name": {"type": TYPE_STRING, "label": "Account Name"},
            "account_type": {
                "type": TYPE_CHOICE,
                "label": "Type",
                "choices": [
                    ("asset", "Asset"),
                    ("liability", "Liability"),
                    ("equity", "Equity"),
                    ("income", "Income"),
                    ("expense", "Expense"),
                ],
            },
            "parent__code": {"type": TYPE_STRING, "label": "Parent Code"},
            "parent__name": {"type": TYPE_STRING, "label": "Parent Name"},
            "opening_balance": {"type": TYPE_DECIMAL, "label": "Opening Balance"},
            "current_balance": {"type": TYPE_DECIMAL, "label": "Current Balance"},
            "is_active": {"type": TYPE_BOOLEAN, "label": "Active"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    "journal_entry": {
        "model": JournalEntry,
        "label": "Journal Entries",
        "icon": "bi-journal-bookmark",
        "company_field": "company",
        "select_related": [],
        "fields": {
            "entry_number": {"type": TYPE_STRING, "label": "Entry #"},
            "entry_date": {"type": TYPE_DATE, "label": "Date"},
            "description": {"type": TYPE_STRING, "label": "Description"},
            "total_debit": {"type": TYPE_DECIMAL, "label": "Total Debit"},
            "total_credit": {"type": TYPE_DECIMAL, "label": "Total Credit"},
            "status": {
                "type": TYPE_CHOICE,
                "label": "Status",
                "choices": [("draft", "Draft"), ("posted", "Posted"), ("reversed", "Reversed")],
            },
            "is_adjusting": {"type": TYPE_BOOLEAN, "label": "Adjusting Entry"},
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
    # ── Services & Quotes ───────────────────────────────────────────────
    "quote": {
        "model": Quote,
        "label": "Quotes",
        "icon": "bi-file-earmark-text",
        "company_field": "company",
        "select_related": ["customer"],
        "fields": {
            "quote_number": {"type": TYPE_STRING, "label": "Quote #"},
            "customer__name": {"type": TYPE_STRING, "label": "Customer"},
            "quote_date": {"type": TYPE_DATE, "label": "Quote Date"},
            "valid_until": {"type": TYPE_DATE, "label": "Valid Until"},
            "subtotal": {"type": TYPE_DECIMAL, "label": "Subtotal"},
            "discount_amount": {"type": TYPE_DECIMAL, "label": "Discount"},
            "tax_amount": {"type": TYPE_DECIMAL, "label": "Tax"},
            "total_amount": {"type": TYPE_DECIMAL, "label": "Total"},
            "status": {
                "type": TYPE_CHOICE,
                "label": "Status",
                "choices": [
                    ("draft", "Draft"),
                    ("sent", "Sent"),
                    ("accepted", "Accepted"),
                    ("rejected", "Rejected"),
                    ("expired", "Expired"),
                ],
            },
            "created_at": {"type": TYPE_DATETIME, "label": "Created"},
        },
    },
}


def get_data_source(key):
    """Return a data source definition or None."""
    return REPORT_DATA_SOURCES.get(key)


def get_all_data_sources_meta():
    """Return metadata for all data sources (for the builder UI).

    Returns a list of dicts, each with a 'key' field, suitable for JS array usage.
    """
    result = []
    for key, src in REPORT_DATA_SOURCES.items():
        fields = []
        for fname, fmeta in src["fields"].items():
            field_info = {
                "key": fname,
                "type": fmeta["type"],
                "label": fmeta["label"],
                "operators": OPERATORS_BY_TYPE.get(fmeta["type"], []),
            }
            if "choices" in fmeta:
                field_info["choices"] = fmeta["choices"]
            fields.append(field_info)

        result.append(
            {
                "key": key,
                "label": src["label"],
                "icon": src["icon"],
                "fields": fields,
                "aggregates": AGGREGATE_FUNCTIONS,
            }
        )
    return result


def validate_configuration(config):
    """Validate a report configuration dict. Returns (is_valid, errors)."""
    errors = []

    data_source_key = config.get("data_source")
    if not data_source_key:
        errors.append("data_source is required.")
        return False, errors

    source = get_data_source(data_source_key)
    if source is None:
        errors.append(f"Unknown data source: {data_source_key}")
        return False, errors

    allowed_fields = set(source["fields"].keys())

    # Validate columns
    columns = config.get("columns", [])
    if not columns:
        errors.append("At least one column is required.")
    for col in columns:
        field = col.get("field")
        if field and field not in allowed_fields:
            errors.append(f"Column field not allowed: {field}")
        aggregate = col.get("aggregate")
        if aggregate and aggregate not in AGGREGATE_FUNCTIONS:
            errors.append(f"Invalid aggregate: {aggregate}")

    # Validate filters
    for flt in config.get("filters", []):
        field = flt.get("field")
        if field and field not in allowed_fields:
            errors.append(f"Filter field not allowed: {field}")
        operator = flt.get("operator")
        if field and operator:
            field_type = source["fields"].get(field, {}).get("type")
            valid_ops = OPERATORS_BY_TYPE.get(field_type, [])
            if operator not in valid_ops:
                errors.append(f"Operator {operator} not valid for field {field} (type {field_type}).")

    # Validate grouping
    for gfield in config.get("grouping", []):
        if gfield not in allowed_fields:
            errors.append(f"Grouping field not allowed: {gfield}")

    # Validate ordering
    for ofield in config.get("ordering", []):
        bare = ofield.lstrip("-")
        if bare not in allowed_fields:
            errors.append(f"Ordering field not allowed: {bare}")

    # Validate limit
    limit = config.get("limit", MAX_REPORT_ROWS)
    if not isinstance(limit, int) or limit < 1:
        errors.append("Limit must be a positive integer.")
    elif limit > MAX_REPORT_ROWS:
        errors.append(f"Limit cannot exceed {MAX_REPORT_ROWS}.")

    return len(errors) == 0, errors
