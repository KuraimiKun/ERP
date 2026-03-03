"""
AI Natural-Language ERP Assistant

Uses OpenAI (or compatible) LLM to let managers query ERP data in
plain Arabic or English.  Generates safe read-only Django ORM queries,
validates them, and returns formatted results.
"""

import ast
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

    # AST node types allowed in generated code
    _ALLOWED_AST_NODES = {
        ast.Module, ast.Expr, ast.Assign, ast.Name, ast.Store, ast.Load,
        ast.Attribute, ast.Call, ast.keyword, ast.Constant,
        ast.List, ast.Tuple, ast.Dict, ast.Set,
        ast.Subscript, ast.Slice, ast.Index,  # Index for older Python
        ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd, ast.Not,
        ast.And, ast.Or,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.In, ast.NotIn, ast.Is, ast.IsNot,
        ast.IfExp, ast.ListComp, ast.SetComp, ast.DictComp,
        ast.GeneratorExp, ast.comprehension,
        ast.JoinedStr, ast.FormattedValue,  # f-strings
        ast.Starred,
    }

    def _validate_code(self, code: str) -> str | None:
        """Return a violation message if code is unsafe, else None.

        Performs two layers of validation:
        1. Regex pattern blocklist (fast reject).
        2. AST whitelist – only explicitly allowed node types pass.
        """
        # Layer 1: regex blocklist
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return f'Forbidden pattern: {pattern}'

        # Layer 2: parse and walk the AST
        try:
            tree = ast.parse(code, mode='exec')
        except SyntaxError as exc:
            return f'Code has syntax errors: {exc}'

        for node in ast.walk(tree):
            if type(node) not in self._ALLOWED_AST_NODES:
                return f'Disallowed construct: {type(node).__name__}'

            # Block dunder attribute access (e.g. __class__, __import__)
            if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
                return f'Access to dunder attribute blocked: {node.attr}'

            # Block calls to non-whitelisted names at the top level
            # (e.g. prevent exec(), eval(), compile(), type() etc.)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in ('exec', 'eval', 'compile', '__import__',
                               'globals', 'locals', 'vars', 'dir',
                               'getattr', 'setattr', 'delattr',
                               'breakpoint', 'exit', 'quit', 'help',
                               'memoryview', 'bytearray', 'bytes',
                               'classmethod', 'staticmethod', 'property',
                               'super', 'type', 'object'):
                    return f'Blocked built-in reference: {node.id}'

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
            # Compile to bytecode first (validated by _validate_code AST check)
            bytecode = compile(code, '<ai-query>', 'exec')  # noqa: S102
            exec(bytecode, {'__builtins__': {}}, namespace)  # noqa: S102
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
