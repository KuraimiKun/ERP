"""
ERP Data Import Service

Provides CSV and Excel import for customers, products, suppliers, employees.
Each entity defines its importable columns, field mappings, and validation logic.
"""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO

from django.db import transaction
from openpyxl import load_workbook

from erp.models import (
    Customer, Product, ProductCategory, Supplier, Employee,
    Department, Currency,
)

# ── Import Registry ─────────────────────────────────────────────────────────
# Each entity maps column headers → (model_field, converter, required)
# converter: callable(raw_value, company) → cleaned value  OR  None for str

def _str(v, _company):
    return str(v).strip() if v is not None else ''

def _str_required(v, _company):
    val = str(v).strip() if v is not None else ''
    if not val:
        raise ValueError('This field is required.')
    return val

def _bool(v, _company):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ('yes', 'true', '1', 'active'):
        return True
    if s in ('no', 'false', '0', 'inactive', ''):
        return False
    raise ValueError(f'Invalid boolean value: {v}')

def _decimal(v, _company):
    if v is None or str(v).strip() == '':
        return Decimal('0')
    try:
        return Decimal(str(v).strip())
    except InvalidOperation:
        raise ValueError(f'Invalid number: {v}')

def _int(v, _company):
    if v is None or str(v).strip() == '':
        return 0
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        raise ValueError(f'Invalid integer: {v}')

def _date(v, _company):
    if v is None or str(v).strip() == '':
        return None
    if isinstance(v, (date, datetime)):
        return v if isinstance(v, date) else v.date()
    s = str(v).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'Invalid date: {v}. Use YYYY-MM-DD format.')

def _date_required(v, company):
    result = _date(v, company)
    if result is None:
        raise ValueError('This field is required.')
    return result

def _currency(v, _company):
    if v is None or str(v).strip() == '':
        return None
    code = str(v).strip().upper()
    try:
        return Currency.objects.get(code=code)
    except Currency.DoesNotExist:
        raise ValueError(f'Currency not found: {code}')

def _currency_required(v, company):
    result = _currency(v, company)
    if result is None:
        raise ValueError('This field is required.')
    return result

def _department(v, company):
    if v is None or str(v).strip() == '':
        return None
    name = str(v).strip()
    try:
        return Department.objects.get(name__iexact=name, company=company)
    except Department.DoesNotExist:
        raise ValueError(f'Department not found: {name}')

def _category(v, company):
    if v is None or str(v).strip() == '':
        return None
    name = str(v).strip()
    try:
        return ProductCategory.objects.get(name__iexact=name, company=company)
    except ProductCategory.DoesNotExist:
        raise ValueError(f'Category not found: {name}')

def _supplier_fk(v, company):
    if v is None or str(v).strip() == '':
        return None
    val = str(v).strip()
    try:
        return Supplier.objects.get(
            company=company,
            supplier_id=val,
        )
    except Supplier.DoesNotExist:
        try:
            return Supplier.objects.get(
                company=company,
                name__iexact=val,
            )
        except (Supplier.DoesNotExist, Supplier.MultipleObjectsReturned):
            raise ValueError(f'Supplier not found: {val}')

def _customer_type(v, _company):
    val = str(v).strip().lower() if v else 'individual'
    valid = {'individual', 'company', 'government'}
    if val not in valid:
        raise ValueError(f'Invalid type: {v}. Must be one of: {", ".join(valid)}')
    return val

def _supplier_type(v, _company):
    val = str(v).strip().lower() if v else ''
    if not val:
        raise ValueError('This field is required.')
    valid = {
        'airline', 'hotel', 'transport', 'visa', 'insurance',
        'tour_operator', 'dmc', 'other',
    }
    if val not in valid:
        raise ValueError(f'Invalid type: {v}. Must be one of: {", ".join(valid)}')
    return val

def _product_type(v, _company):
    val = str(v).strip().lower() if v else 'physical'
    valid = {'physical', 'digital', 'consumable', 'raw_material'}
    if val not in valid:
        raise ValueError(f'Invalid type: {v}. Must be one of: {", ".join(valid)}')
    return val

def _employment_type(v, _company):
    val = str(v).strip().lower() if v else 'full_time'
    valid = {'full_time', 'part_time', 'contract', 'intern', 'freelance'}
    if val not in valid:
        raise ValueError(f'Invalid type: {v}. Must be one of: {", ".join(valid)}')
    return val

def _employment_status(v, _company):
    val = str(v).strip().lower() if v else 'active'
    valid = {'active', 'on_leave', 'suspended', 'terminated', 'resigned'}
    if val not in valid:
        raise ValueError(f'Invalid status: {v}. Must be one of: {", ".join(valid)}')
    return val

def _gender(v, _company):
    val = str(v).strip().lower() if v else ''
    if not val:
        raise ValueError('This field is required.')
    if val in ('male', 'm'):
        return 'male'
    if val in ('female', 'f'):
        return 'female'
    raise ValueError(f'Invalid gender: {v}. Must be male or female.')


# ── Column mappings per entity ──────────────────────────────────────────────
# key = normalised header, value = (model_field, converter)

IMPORT_REGISTRY = {
    'customers': {
        'model': Customer,
        'unique_field': 'customer_id',
        'company_field': 'company',
        'columns': {
            'customer id':    ('customer_id',      _str_required),
            'name':           ('name',             _str_required),
            'name (ar)':      ('name_ar',          _str),
            'type':           ('customer_type',    _customer_type),
            'email':          ('email',            _str),
            'phone':          ('phone',            _str),
            'mobile':         ('mobile',           _str),
            'tax id':         ('tax_id',           _str),
            'credit limit':   ('credit_limit',     _decimal),
            'payment terms':  ('payment_terms',    _int),
            'payment terms (days)': ('payment_terms', _int),
            'currency':       ('currency',         _currency),
            'city':           ('billing_city',     _str),
            'country':        ('billing_country',  _str),
            'active':         ('is_active',        _bool),
        },
    },
    'products': {
        'model': Product,
        'unique_field': 'sku',
        'company_field': 'company',
        'columns': {
            'sku':            ('sku',              _str_required),
            'barcode':        ('barcode',          _str),
            'name':           ('name',             _str_required),
            'name (ar)':      ('name_ar',          _str),
            'type':           ('product_type',     _product_type),
            'category':       ('category',         _category),
            'selling price':  ('selling_price',    _decimal),
            'cost price':     ('cost_price',       _decimal),
            'quantity on hand': ('quantity_on_hand', _decimal),
            'reorder level':  ('reorder_level',    _decimal),
            'supplier':       ('supplier',         _supplier_fk),
            'currency':       ('currency',         _currency_required),
            'active':         ('is_active',        _bool),
        },
    },
    'suppliers': {
        'model': Supplier,
        'unique_field': 'supplier_id',
        'company_field': 'company',
        'columns': {
            'supplier id':    ('supplier_id',      _str_required),
            'name':           ('name',             _str_required),
            'name (ar)':      ('name_ar',          _str),
            'type':           ('supplier_type',    _supplier_type),
            'email':          ('email',            _str),
            'phone':          ('phone',            _str),
            'contact person': ('contact_person',   _str),
            'city':           ('city',             _str),
            'country':        ('country',          _str),
            'tax number':     ('tax_number',       _str),
            'currency':       ('currency',         _currency),
            'active':         ('is_active',        _bool),
        },
    },
    'employees': {
        'model': Employee,
        'unique_field': 'employee_id',
        'company_field': 'company',
        'columns': {
            'employee id':      ('employee_id',       _str_required),
            'first name':       ('first_name',        _str_required),
            'last name':        ('last_name',         _str_required),
            'email':            ('email',             _str_required),
            'phone':            ('phone',             _str_required),
            'gender':           ('gender',            _gender),
            'date of birth':    ('date_of_birth',     _date_required),
            'nationality':      ('nationality',       _str_required),
            'department':       ('department',        _department),
            'job title':        ('job_title',         _str_required),
            'employment type':  ('employment_type',   _employment_type),
            'status':           ('employment_status', _employment_status),
            'hire date':        ('hire_date',         _date_required),
            'basic salary':     ('basic_salary',      _decimal),
            'currency':         ('currency',          _currency_required),
        },
    },
}


# ── Parsing helpers ─────────────────────────────────────────────────────────

def _normalise_header(h):
    """Lower-case, strip whitespace for header matching."""
    return str(h).strip().lower()


def parse_file(uploaded_file):
    """
    Parse an uploaded CSV or Excel file and return (headers, rows).

    headers: list[str] – original header strings
    rows: list[list] – cell values per row
    """
    name = uploaded_file.name.lower()
    if name.endswith('.csv'):
        return _parse_csv(uploaded_file)
    if name.endswith(('.xlsx', '.xls')):
        return _parse_excel(uploaded_file)
    raise ValueError('Unsupported file format. Please upload a CSV or Excel (.xlsx) file.')


def _parse_csv(uploaded_file):
    content = uploaded_file.read()
    # Try UTF-8 first, then latin-1
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('Unable to decode file. Please ensure it is UTF-8 encoded.')

    reader = csv.reader(StringIO(text))
    rows_list = list(reader)
    if not rows_list:
        raise ValueError('The file is empty.')
    headers = rows_list[0]
    data_rows = [r for r in rows_list[1:] if any(cell.strip() for cell in r)]
    return headers, data_rows


def _parse_excel(uploaded_file):
    content = uploaded_file.read()
    wb = load_workbook(filename=BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows_list = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows_list:
        raise ValueError('The file is empty.')
    headers = [str(h) if h is not None else '' for h in rows_list[0]]
    data_rows = [
        list(r) for r in rows_list[1:]
        if any(c is not None and str(c).strip() for c in r)
    ]
    return headers, data_rows


# ── Validation ──────────────────────────────────────────────────────────────

def validate_rows(entity, headers, rows, company):
    """
    Validate each row against the entity's column definitions.

    Returns:
        preview_rows: list of dicts with 'row_num', 'data' (dict of field→value),
                      'errors' (dict of field→error message)
        mapped_headers: list of (header, model_field_or_None) for display
        has_errors: bool
    """
    config = IMPORT_REGISTRY[entity]
    col_map = config['columns']

    # Map file headers → column config
    header_mapping = []  # list of (original_header, model_field, converter) or None
    for h in headers:
        norm = _normalise_header(h)
        if norm in col_map:
            field_name, converter = col_map[norm]
            header_mapping.append((h, field_name, converter))
        else:
            header_mapping.append((h, None, None))

    mapped_fields = [(h, f) for h, f, _ in header_mapping]

    # Check that at least the unique field is present
    unique_field = config['unique_field']
    mapped_field_names = {f for _, f, _ in header_mapping if f}
    if unique_field not in mapped_field_names:
        raise ValueError(
            f'Required column for "{unique_field}" not found in file headers. '
            f'Expected headers include: {", ".join(col_map.keys())}'
        )

    preview_rows = []
    has_errors = False

    existing_unique_values = set(
        config['model'].objects.filter(
            **{config['company_field']: company}
        ).values_list(unique_field, flat=True)
    )

    for row_idx, row in enumerate(rows, start=2):  # Row 2 = first data row
        row_data = {}
        row_errors = {}

        for col_idx, (orig_header, field_name, converter) in enumerate(header_mapping):
            if field_name is None:
                continue  # Unmapped column, skip

            raw_value = row[col_idx] if col_idx < len(row) else None
            try:
                cleaned = converter(raw_value, company)
                row_data[field_name] = cleaned
            except ValueError as e:
                row_errors[field_name] = str(e)
                row_data[field_name] = raw_value
                has_errors = True

        # Check for duplicate unique field within company
        unique_val = row_data.get(unique_field, '')
        if unique_val and unique_val in existing_unique_values:
            row_data['_is_update'] = True
        else:
            row_data['_is_update'] = False
            if unique_val:
                existing_unique_values.add(unique_val)

        preview_rows.append({
            'row_num': row_idx,
            'data': row_data,
            'errors': row_errors,
        })

    return preview_rows, mapped_fields, has_errors


# ── Import execution ────────────────────────────────────────────────────────

def execute_import(entity, headers, rows, company, user):
    """
    Parse, validate, and import rows.

    Returns: (created_count, updated_count, error_rows)
    """
    config = IMPORT_REGISTRY[entity]
    col_map = config['columns']
    model = config['model']
    unique_field = config['unique_field']

    header_mapping = []
    for h in headers:
        norm = _normalise_header(h)
        if norm in col_map:
            field_name, converter = col_map[norm]
            header_mapping.append((h, field_name, converter))
        else:
            header_mapping.append((h, None, None))

    created = 0
    updated = 0
    error_rows = []
    seen_unique_vals = set()

    with transaction.atomic():
        for row_idx, row in enumerate(rows, start=2):
            row_data = {}
            row_errors = {}

            for col_idx, (orig_header, field_name, converter) in enumerate(header_mapping):
                if field_name is None:
                    continue
                raw_value = row[col_idx] if col_idx < len(row) else None
                try:
                    cleaned = converter(raw_value, company)
                    row_data[field_name] = cleaned
                except ValueError as e:
                    row_errors[field_name] = str(e)

            if row_errors:
                error_rows.append({'row_num': row_idx, 'errors': row_errors})
                continue

            unique_val = row_data.get(unique_field)
            if not unique_val:
                error_rows.append({
                    'row_num': row_idx,
                    'errors': {unique_field: 'Required field is empty.'},
                })
                continue

            # Detect intra-file duplicates
            if unique_val in seen_unique_vals:
                error_rows.append({
                    'row_num': row_idx,
                    'errors': {unique_field: f'Duplicate value "{unique_val}" already in this file.'},
                })
                continue
            seen_unique_vals.add(unique_val)

            # Try to find existing record
            try:
                obj = model.objects.get(
                    **{config['company_field']: company, unique_field: unique_val}
                )
                # Update existing
                for field, value in row_data.items():
                    if field.startswith('_'):
                        continue
                    setattr(obj, field, value)
                if hasattr(obj, 'updated_by'):
                    obj.updated_by = user
                obj.save()
                updated += 1
            except model.DoesNotExist:
                # Create new
                row_data[config['company_field']] = company
                # Remove internal keys
                clean_data = {k: v for k, v in row_data.items() if not k.startswith('_')}
                obj = model(**clean_data)
                if hasattr(obj, 'created_by'):
                    obj.created_by = user
                if hasattr(obj, 'updated_by'):
                    obj.updated_by = user
                obj.save()
                created += 1

    return created, updated, error_rows


def get_sample_headers(entity):
    """Return the expected column headers for an entity."""
    config = IMPORT_REGISTRY[entity]
    return [h.title() for h in config['columns'].keys()]
