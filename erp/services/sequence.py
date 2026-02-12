"""
ERP Services - Sequence Number Generator

Provides automatic sequence number generation for documents like
invoices, purchase orders, payments, etc.
"""

from django.db import transaction
from django.utils import timezone
from ..models import Sequence


class SequenceService:
    """Service for generating sequential document numbers."""
    
    @staticmethod
    @transaction.atomic
    def get_next_number(company, sequence_name):
        """
        Get the next number in a sequence.
        
        Args:
            company: The company instance
            sequence_name: Name of the sequence (e.g., 'invoice', 'payment', 'po')
        
        Returns:
            str: The formatted sequence number (e.g., 'INV-2024-00001')
        """
        try:
            # Lock the sequence row for update
            sequence = Sequence.objects.select_for_update().get(
                company=company,
                name=sequence_name
            )
        except Sequence.DoesNotExist:
            # Create default sequence if it doesn't exist
            sequence = Sequence.objects.create(
                company=company,
                name=sequence_name,
                prefix=sequence_name.upper()[:3] + '-',
                current_number=0,
                padding=5
            )
        
        # Check if we need to reset (annually)
        current_year = timezone.now().year
        if sequence.reset_annually and sequence.last_reset_year != current_year:
            sequence.current_number = 0
            sequence.last_reset_year = current_year
        
        # Increment the number
        sequence.current_number += 1
        sequence.save()
        
        # Format the number
        return sequence.get_formatted_number()
    
    @staticmethod
    def create_sequence(company, name, prefix='', suffix='', padding=5, reset_annually=True):
        """
        Create a new sequence for a company.
        
        Args:
            company: The company instance
            name: Unique name for the sequence
            prefix: Prefix for the number (e.g., 'INV-')
            suffix: Suffix for the number
            padding: Number of digits to pad to
            reset_annually: Whether to reset the sequence each year
        
        Returns:
            Sequence: The created sequence instance
        """
        return Sequence.objects.create(
            company=company,
            name=name,
            prefix=prefix,
            suffix=suffix,
            padding=padding,
            reset_annually=reset_annually,
            current_number=0,
            last_reset_year=timezone.now().year
        )
    
    @staticmethod
    def preview_next_number(company, sequence_name):
        """
        Preview what the next number would be without incrementing.
        
        Args:
            company: The company instance
            sequence_name: Name of the sequence
        
        Returns:
            str: The next formatted sequence number (preview only)
        """
        try:
            sequence = Sequence.objects.get(
                company=company,
                name=sequence_name
            )
            # Temporarily increment for preview
            next_num = sequence.current_number + 1
            
            # Build the formatted number
            prefix = sequence.prefix
            if sequence.include_year and sequence.reset_annually:
                prefix += str(timezone.now().year) + '-'
            
            padded_number = str(next_num).zfill(sequence.padding)
            return f"{prefix}{padded_number}{sequence.suffix}"
            
        except Sequence.DoesNotExist:
            return f"{sequence_name.upper()[:3]}-{timezone.now().year}-00001"


# Convenience functions for common sequences
def get_invoice_number(company):
    """Get next invoice number."""
    return SequenceService.get_next_number(company, 'invoice')


def get_payment_number(company):
    """Get next payment number."""
    return SequenceService.get_next_number(company, 'payment')


def get_po_number(company):
    """Get next purchase order number."""
    return SequenceService.get_next_number(company, 'purchase_order')


def get_expense_number(company):
    """Get next expense number."""
    return SequenceService.get_next_number(company, 'expense')


def get_quote_number(company):
    """Get next quote number."""
    return SequenceService.get_next_number(company, 'quote')


def get_lead_number(company):
    """Get next lead number."""
    return SequenceService.get_next_number(company, 'lead')


def get_customer_id(company):
    """Get next customer ID."""
    return SequenceService.get_next_number(company, 'customer')


def get_supplier_id(company):
    """Get next supplier ID."""
    return SequenceService.get_next_number(company, 'supplier')


def get_employee_id(company):
    """Get next employee ID."""
    return SequenceService.get_next_number(company, 'employee')
