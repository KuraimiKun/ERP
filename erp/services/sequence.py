"""
ERP Services - Sequence Number Generator

Provides automatic sequence number generation for documents like
invoices, purchase orders, payments, etc.

Delegates to the ``Sequence.get_next()`` model method which handles
reset logic and formatting.
"""

from django.db import transaction
from django.utils import timezone

from tenants.routers import get_current_db_alias
from ..models import Sequence


# Map convenience names → Sequence.SequenceType values
_SEQUENCE_TYPE_MAP = {
    "invoice": Sequence.SequenceType.INVOICE,
    "payment": Sequence.SequenceType.PAYMENT,
    "expense": Sequence.SequenceType.EXPENSE,
    "quote": Sequence.SequenceType.QUOTATION,
    "quotation": Sequence.SequenceType.QUOTATION,
    "purchase_order": Sequence.SequenceType.PURCHASE_ORDER,
    "employee": Sequence.SequenceType.EMPLOYEE,
    "customer": Sequence.SequenceType.CUSTOMER,
    "supplier": Sequence.SequenceType.SUPPLIER,
    "supplier_invoice": Sequence.SequenceType.SUPPLIER_INVOICE,
    "supplier_payment": Sequence.SequenceType.SUPPLIER_PAYMENT,
    "lead": Sequence.SequenceType.LEAD,
    "pos_order": Sequence.SequenceType.POS_ORDER,
    "pos_session": Sequence.SequenceType.POS_SESSION,
}

# Default prefixes when auto-creating a missing sequence
_DEFAULT_PREFIXES = {
    "invoice": "INV-",
    "payment": "PAY-",
    "expense": "EXP-",
    "quote": "QUO-",
    "quotation": "QUO-",
    "purchase_order": "PO-",
    "employee": "EMP-",
    "customer": "CUS-",
    "supplier": "SUP-",
    "supplier_invoice": "SINV-",
    "supplier_payment": "SPAY-",
    "lead": "LD-",
    "pos_order": "POS-",
    "pos_session": "SESS-",
}


class SequenceService:
    """Service for generating sequential document numbers."""

    @staticmethod
    def get_next_number(company, sequence_name):
        """
        Get the next number in a sequence.

        Args:
            company: The company instance
            sequence_name: Friendly name (e.g. 'invoice', 'customer')

        Returns:
            str: The formatted sequence number (e.g. 'CUS-00001')
        """
        seq_type = _SEQUENCE_TYPE_MAP.get(sequence_name, sequence_name)
        db_alias = get_current_db_alias()

        with transaction.atomic(using=db_alias):
            try:
                sequence = (
                    Sequence.objects.using(db_alias)
                    .select_for_update()
                    .get(
                        company=company,
                        sequence_type=seq_type,
                    )
                )
            except Sequence.DoesNotExist:
                sequence = Sequence.objects.using(db_alias).create(
                    company=company,
                    sequence_type=seq_type,
                    prefix=_DEFAULT_PREFIXES.get(sequence_name, seq_type.upper()[:3] + "-"),
                    padding=5,
                    reset_period="never",
                    last_reset=timezone.now().date(),
                )

            return sequence.get_next()

    @staticmethod
    def create_sequence(
        company,
        sequence_name,
        prefix="",
        suffix="",
        padding=5,
        reset_period="never",
    ):
        """Create a new sequence for a company."""
        seq_type = _SEQUENCE_TYPE_MAP.get(sequence_name, sequence_name)
        return Sequence.objects.create(
            company=company,
            sequence_type=seq_type,
            prefix=prefix,
            suffix=suffix,
            padding=padding,
            reset_period=reset_period,
            last_reset=timezone.now().date(),
        )

    @staticmethod
    def preview_next_number(company, sequence_name):
        """Preview the next number without incrementing."""
        seq_type = _SEQUENCE_TYPE_MAP.get(sequence_name, sequence_name)
        try:
            sequence = Sequence.objects.get(
                company=company,
                sequence_type=seq_type,
            )
            number = str(sequence.next_number).zfill(sequence.padding)
            return f"{sequence.prefix}{number}{sequence.suffix}"
        except Sequence.DoesNotExist:
            prefix = _DEFAULT_PREFIXES.get(sequence_name, seq_type.upper()[:3] + "-")
            return f"{prefix}00001"


# ── Convenience helpers ─────────────────────────────────────────────────────


def get_invoice_number(company):
    """Get next invoice number."""
    return SequenceService.get_next_number(company, "invoice")


def get_payment_number(company):
    """Get next payment number."""
    return SequenceService.get_next_number(company, "payment")


def get_po_number(company):
    """Get next purchase order number."""
    return SequenceService.get_next_number(company, "purchase_order")


def get_expense_number(company):
    """Get next expense number."""
    return SequenceService.get_next_number(company, "expense")


def get_quote_number(company):
    """Get next quote number."""
    return SequenceService.get_next_number(company, "quote")


def get_lead_number(company):
    """Get next lead number."""
    return SequenceService.get_next_number(company, "lead")


def get_customer_id(company):
    """Get next customer ID."""
    return SequenceService.get_next_number(company, "customer")


def get_supplier_id(company):
    """Get next supplier ID."""
    return SequenceService.get_next_number(company, "supplier")


def get_supplier_invoice_number(company):
    """Get next supplier invoice number."""
    return SequenceService.get_next_number(company, "supplier_invoice")


def get_supplier_payment_number(company):
    """Get next supplier payment number."""
    return SequenceService.get_next_number(company, "supplier_payment")


def get_employee_id(company):
    """Get next employee ID."""
    return SequenceService.get_next_number(company, "employee")


def get_pos_order_number(company):
    """Get next POS order number."""
    return SequenceService.get_next_number(company, "pos_order")


def get_pos_session_number(company):
    """Get next POS session number."""
    return SequenceService.get_next_number(company, "pos_session")
