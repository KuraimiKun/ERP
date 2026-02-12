"""
ERP Services Package

This package contains all business logic services for the ERP system.
"""

from .sequence import (
    SequenceService,
    get_invoice_number,
    get_payment_number,
    get_po_number,
    get_expense_number,
    get_quote_number,
    get_lead_number,
    get_customer_id,
    get_supplier_id,
    get_employee_id,
)

from .audit import (
    AuditService,
    AuditMiddleware,
    get_field_changes,
)

from .notification import (
    NotificationService,
    notify_task_assigned,
    notify_leave_request,
    notify_expense_approval,
    notify_invoice_paid,
)

__all__ = [
    # Sequence
    'SequenceService',
    'get_invoice_number',
    'get_payment_number',
    'get_po_number',
    'get_expense_number',
    'get_quote_number',
    'get_lead_number',
    'get_customer_id',
    'get_supplier_id',
    'get_employee_id',
    
    # Audit
    'AuditService',
    'AuditMiddleware',
    'get_field_changes',
    
    # Notification
    'NotificationService',
    'notify_task_assigned',
    'notify_leave_request',
    'notify_expense_approval',
    'notify_invoice_paid',
]
