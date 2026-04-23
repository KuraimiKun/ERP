"""
Financial Reports — pure computation layer.

Thin, side-effect-free helpers that compute the numbers behind the four
standard statements (Trial Balance, Profit & Loss, Balance Sheet, Cash
Flow) from the posted ``JournalEntryLine`` / ``Payment`` / ``Expense``
tables.  Used by both the server-rendered HTML views and the JSON API.

All queries are scoped to a single ``Company`` and respect the posting
status on journal entries.  Amounts are returned as ``Decimal``.
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal
from typing import Any, Iterable

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
)
from django.db.models.functions import Coalesce

# Module-local Decimal zero to keep type-stability in aggregates / sums.
_ZERO = Decimal("0")

# Multi-currency helper: values are stored with a snapshot exchange rate so
# that historical totals don't shift when today's rate changes.
_AMOUNT_BASE = ExpressionWrapper(
    F("amount") * F("exchange_rate_at_date"),
    output_field=DecimalField(max_digits=20, decimal_places=6),
)
_TOTAL_BASE = ExpressionWrapper(
    F("total_amount") * F("exchange_rate_at_date"),
    output_field=DecimalField(max_digits=20, decimal_places=6),
)


def _get_account_balances(
    company,
    start_date: _date,
    end_date: _date,
    account_types: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Aggregate posted journal entry lines by account for a date range.

    Returns a list of dicts — one per account that had activity in the
    window — with ``debit``, ``credit`` and a signed ``balance`` (in normal-
    balance direction for the account type).
    """
    # Imported lazily so this module can be imported at Django-startup time
    # without forcing app registry initialisation.
    from erp.models import JournalEntryLine

    qs = JournalEntryLine.objects.filter(
        journal_entry__company=company,
        journal_entry__status="posted",
        journal_entry__entry_date__gte=start_date,
        journal_entry__entry_date__lte=end_date,
    ).select_related("account")

    if account_types:
        qs = qs.filter(account__account_type__in=list(account_types))

    # After .values().annotate() the queryset yields dicts, but typing still
    # tracks it as QuerySet[JournalEntryLine].  Cast to Any to silence
    # indexing errors without disabling the whole module.
    dict_rows: Any = (
        qs.values(
            "account__id",
            "account__code",
            "account__name",
            "account__name_ar",
            "account__account_type",
        )
        .annotate(
            total_debit=Coalesce(Sum("debit_amount"), _ZERO),
            total_credit=Coalesce(Sum("credit_amount"), _ZERO),
        )
        .order_by("account__code")
    )

    results: list[dict[str, Any]] = []
    for row in dict_rows:
        acct_type = row["account__account_type"]
        debit = row["total_debit"]
        credit = row["total_credit"]
        # Normal balance: assets/expenses are debit-normal; the rest credit-normal.
        if acct_type in ("asset", "expense"):
            balance = debit - credit
        else:
            balance = credit - debit
        results.append(
            {
                "id": row["account__id"],
                "code": row["account__code"],
                "name": row["account__name"],
                "name_ar": row["account__name_ar"],
                "account_type": acct_type,
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )
    return results


# ── Statements ─────────────────────────────────────────────────────────────


def trial_balance(company, start_date: _date, end_date: _date) -> dict[str, Any]:
    """Trial Balance for the period ``[start_date, end_date]``."""
    accounts = _get_account_balances(company, start_date, end_date)
    total_debit = sum((a["debit"] for a in accounts), _ZERO)
    total_credit = sum((a["credit"] for a in accounts), _ZERO)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "accounts": accounts,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": total_debit == total_credit,
    }


def profit_and_loss(company, start_date: _date, end_date: _date) -> dict[str, Any]:
    """Profit & Loss for the period."""
    income_accounts = _get_account_balances(company, start_date, end_date, ["income"])
    expense_accounts = _get_account_balances(company, start_date, end_date, ["expense"])
    total_income = sum((a["balance"] for a in income_accounts), _ZERO)
    total_expenses = sum((a["balance"] for a in expense_accounts), _ZERO)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "income_accounts": income_accounts,
        "expense_accounts": expense_accounts,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
    }


# Sentinel "start of time" used for cumulative balance-sheet queries.  Chosen
# well before any tenant could have fiscal data yet safely representable as
# a proper ISO date.
_EPOCH = _date(2000, 1, 1)


def balance_sheet(company, as_of_date: _date) -> dict[str, Any]:
    """Balance Sheet as of ``as_of_date`` (cumulative from inception)."""
    asset_accounts = _get_account_balances(company, _EPOCH, as_of_date, ["asset"])
    liability_accounts = _get_account_balances(company, _EPOCH, as_of_date, ["liability"])
    equity_accounts = _get_account_balances(company, _EPOCH, as_of_date, ["equity"])

    income_accounts = _get_account_balances(company, _EPOCH, as_of_date, ["income"])
    expense_accounts = _get_account_balances(company, _EPOCH, as_of_date, ["expense"])
    retained_earnings = sum((a["balance"] for a in income_accounts), _ZERO) - sum(
        (a["balance"] for a in expense_accounts), _ZERO
    )

    total_assets = sum((a["balance"] for a in asset_accounts), _ZERO)
    total_liabilities = sum((a["balance"] for a in liability_accounts), _ZERO)
    total_equity = sum((a["balance"] for a in equity_accounts), _ZERO) + retained_earnings
    return {
        "as_of_date": as_of_date,
        "asset_accounts": asset_accounts,
        "liability_accounts": liability_accounts,
        "equity_accounts": equity_accounts,
        "retained_earnings": retained_earnings,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        # Should equal zero for a well-formed book.  Non-zero = data problem.
        "balance_check": total_assets - (total_liabilities + total_equity),
    }


def cash_flow(company, start_date: _date, end_date: _date) -> dict[str, Any]:
    """Simplified cash flow — operating activities only.

    Tracks only the cash legs that the ERP explicitly models today:
      - Payments received from customers (inflow)
      - Supplier payments (outflow, if model present)
      - Expenses in ``approved`` / ``paid`` status (outflow)
    """
    from erp.models import Payment, Expense

    payments_received = Payment.objects.filter(
        company=company,
        payment_date__gte=start_date,
        payment_date__lte=end_date,
        payment_type="received",
    ).aggregate(total=Coalesce(Sum(_AMOUNT_BASE), _ZERO))["total"]

    payments_made_supplier = _ZERO
    try:
        from erp.models import SupplierPayment as _SupplierPayment
    except ImportError:
        _SupplierPayment = None  # type: ignore[assignment,misc]
    if _SupplierPayment is not None:
        payments_made_supplier = _SupplierPayment.objects.filter(
            company=company,
            payment_date__gte=start_date,
            payment_date__lte=end_date,
        ).aggregate(total=Coalesce(Sum(_AMOUNT_BASE), _ZERO))["total"]

    expenses_paid = Expense.objects.filter(
        company=company,
        expense_date__gte=start_date,
        expense_date__lte=end_date,
        status__in=["approved", "paid"],
    ).aggregate(total=Coalesce(Sum(_TOTAL_BASE), _ZERO))["total"]

    operating_inflows = payments_received
    operating_outflows = payments_made_supplier + expenses_paid
    net_operating = operating_inflows - operating_outflows
    return {
        "start_date": start_date,
        "end_date": end_date,
        "payments_received": payments_received,
        "payments_made_supplier": payments_made_supplier,
        "expenses_paid": expenses_paid,
        "operating_inflows": operating_inflows,
        "operating_outflows": operating_outflows,
        "net_operating": net_operating,
        # Simplified: no investing / financing activities modelled yet.
        "net_cash_change": net_operating,
    }
