"""
AI Natural-Language ERP Assistant

Uses OpenAI (or compatible) LLM to let managers query ERP data in
plain Arabic or English.  Generates safe read-only Django ORM queries,
validates them, and returns formatted results.
"""

import json
import logging
import re
import textwrap
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum, Count, Avg, Max, Min, Q
from django.utils import timezone

from erp.models import (
    Invoice, Payment, Expense, Customer, Lead, Employee, Product,
    StockMovement, PurchaseOrder, Quote, Attendance, Payroll,
    Account, JournalEntry,
)

logger = logging.getLogger('erp.ai.assistant')

SYSTEM_PROMPT = textwrap.dedent("""\
You are an ERP data assistant embedded in a Django ERP system.
You MUST generate **safe, read-only** Django ORM Python code to answer the user's question.

Available Django models (all scoped to the company automatically):
- Invoice       (company, customer, total_amount, balance_due, status, invoice_date, due_date, invoice_number)
- Payment       (company, customer, amount, payment_date, payment_method)
- Expense       (company, total_amount, status, expense_date, category, employee)
- Customer      (company, name, name_ar, email, phone, customer_type, is_active)
- Lead          (company, first_name, last_name, email, status, source, estimated_value, probability, assigned_to)
- Employee      (company, first_name, last_name, department, employment_status, basic_salary, hire_date)
- Product       (company, name, sku, unit_price, is_active)
- StockMovement (company, product, warehouse, quantity, movement_type, created_at)
- PurchaseOrder (company, supplier, total_amount, status, order_date)
- Quote         (company, customer, total_amount, status)
- Attendance    (employee, date, check_in, check_out)
- Payroll       (employee, period_start, period_end, net_salary, status)
- Account       (company, code, name, account_type, current_balance)

Rules:
1. Always filter by company=company (variable already in scope).
2. Use ONLY aggregation queries (Sum, Count, Avg, Max, Min, filter, values, order_by).
3. NEVER use .delete(), .update(), .create(), save(), raw(), or execute().
4. NEVER import os, subprocess, sys, or any module.
5. Assign the final result to a variable called `result`.
6. `result` must be a JSON-serialisable Python object (dict, list, int, float, str, Decimal).
7. Reply with ONLY the Python code block, no explanation.
""")


class ERPAssistant:
    """LLM-powered natural-language query interface for ERP data."""

    ALLOWED_MODELS = {
        'Invoice', 'Payment', 'Expense', 'Customer', 'Lead',
        'Employee', 'Product', 'StockMovement', 'PurchaseOrder',
        'Quote', 'Attendance', 'Payroll', 'Account', 'JournalEntry',
    }

    FORBIDDEN_PATTERNS = [
        r'\bdelete\b', r'\bupdate\b', r'\bcreate\b', r'\bsave\b',
        r'\braw\b', r'\bexecute\b', r'\bimport\b', r'\bexec\b',
        r'\beval\b', r'\b__\b', r'\bos\b', r'\bsys\b', r'\bsubprocess\b',
        r'\bopen\b', r'\bwrite\b', r'\brm\b',
    ]

    def __init__(self, company, user=None):
        self.company = company
        self.user = user

    def query(self, question: str) -> dict:
        """Process a natural-language question and return the answer.

        Returns dict with keys: answer, code, error (if any).
        """
        # Per-tenant API key from Company model, fall back to global setting
        api_key = getattr(self.company, 'openai_api_key', '') or getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            return {
                'answer': 'AI assistant is not configured. '
                          'Please set your OpenAI API key in Company → AI Settings.',
                'code': '',
                'error': 'missing_api_key',
            }

        # Check if AI is enabled for this tenant
        if not getattr(self.company, 'ai_enabled', True):
            return {
                'answer': 'AI features are disabled for this company. '
                          'Enable them in Company → AI Settings.',
                'code': '',
                'error': 'ai_disabled',
            }

        try:
            import openai
        except ImportError:
            return {
                'answer': 'OpenAI library is not installed.',
                'code': '',
                'error': 'missing_openai',
            }

        # Call the LLM
        model_name = getattr(self.company, 'openai_model', '') or 'gpt-4o-mini'
        client = openai.OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': question},
                ],
                temperature=0,
                max_tokens=1024,
            )
            code = response.choices[0].message.content.strip()
        except Exception as exc:
            logger.exception('OpenAI API call failed: %s', exc)
            return {
                'answer': f'LLM API error: {exc}',
                'code': '',
                'error': 'api_error',
            }

        # Extract code from markdown fences if present
        code = self._extract_code(code)

        # Safety validation
        violation = self._validate_code(code)
        if violation:
            return {
                'answer': f'Generated code was rejected for safety: {violation}',
                'code': code,
                'error': 'unsafe_code',
            }

        # Execute safely
        return self._execute(code)

    def _extract_code(self, text: str) -> str:
        """Strip markdown code fences."""
        match = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _validate_code(self, code: str) -> str | None:
        """Return a violation message if code is unsafe, else None."""
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return f'Forbidden pattern: {pattern}'
        return None

    def _execute(self, code: str) -> dict:
        """Execute generated ORM code in a sandboxed namespace."""
        namespace = {
            # Models
            'Invoice': Invoice,
            'Payment': Payment,
            'Expense': Expense,
            'Customer': Customer,
            'Lead': Lead,
            'Employee': Employee,
            'Product': Product,
            'StockMovement': StockMovement,
            'PurchaseOrder': PurchaseOrder,
            'Quote': Quote,
            'Attendance': Attendance,
            'Payroll': Payroll,
            'Account': Account,
            'JournalEntry': JournalEntry,
            # Aggregations
            'Sum': Sum,
            'Count': Count,
            'Avg': Avg,
            'Max': Max,
            'Min': Min,
            'Q': Q,
            # Context
            'company': self.company,
            'timezone': timezone,
            'Decimal': Decimal,
            # Built-ins (restricted)
            'range': range,
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'list': list,
            'dict': dict,
            'round': round,
            'sorted': sorted,
            'abs': abs,
            'min': min,
            'max': max,
            'result': None,
        }

        try:
            exec(code, {'__builtins__': {}}, namespace)  # noqa: S102
        except Exception as exc:
            logger.warning('Generated code execution failed: %s\nCode:\n%s',
                           exc, code)
            return {
                'answer': f'Query execution error: {exc}',
                'code': code,
                'error': 'execution_error',
            }

        result = namespace.get('result')

        # Serialise Decimal and date objects
        answer = self._serialise(result)

        return {
            'answer': answer,
            'code': code,
            'error': None,
        }

    def _serialise(self, obj):
        """Convert ORM / Decimal results to JSON-safe types."""
        if obj is None:
            return 'No results found.'
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (list, tuple)):
            return [self._serialise(item) for item in obj]
        if isinstance(obj, dict):
            return {k: self._serialise(v) for k, v in obj.items()}
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if isinstance(obj, (int, float, str, bool)):
            return obj
        return str(obj)
