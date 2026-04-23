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
    get_supplier_invoice_number,
    get_supplier_payment_number,
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

from .accounting import (
    create_invoice_journal_entry,
    create_payment_journal_entry,
    create_expense_journal_entry,
    create_supplier_invoice_journal_entry,
    create_supplier_payment_journal_entry,
    create_purchase_order_journal_entry,
)

from .inventory import (
    record_stock_movement,
    confirm_goods_receipt,
    ship_stock_transfer,
    receive_stock_transfer,
    approve_stock_adjustment,
    complete_cycle_count,
    complete_pick_list,
    ship_shipment,
    get_reorder_suggestions,
    get_stock_summary_by_warehouse,
    get_stock_summary_by_product,
)

from .inventory_accounting import (
    create_grn_journal_entry,
    create_sales_issue_journal_entry,
    create_adjustment_journal_entry,
)

__all__ = [
    # Sequence
    "SequenceService",
    "get_invoice_number",
    "get_payment_number",
    "get_po_number",
    "get_expense_number",
    "get_quote_number",
    "get_lead_number",
    "get_customer_id",
    "get_supplier_id",
    "get_supplier_invoice_number",
    "get_supplier_payment_number",
    "get_employee_id",
    # Audit
    "AuditService",
    "AuditMiddleware",
    "get_field_changes",
    # Notification
    "NotificationService",
    "notify_task_assigned",
    "notify_leave_request",
    "notify_expense_approval",
    "notify_invoice_paid",
    # Accounting
    "create_invoice_journal_entry",
    "create_payment_journal_entry",
    "create_expense_journal_entry",
    "create_supplier_invoice_journal_entry",
    "create_supplier_payment_journal_entry",
    "create_purchase_order_journal_entry",
    # Inventory
    "record_stock_movement",
    "confirm_goods_receipt",
    "ship_stock_transfer",
    "receive_stock_transfer",
    "approve_stock_adjustment",
    "complete_cycle_count",
    "complete_pick_list",
    "ship_shipment",
    "get_reorder_suggestions",
    "get_stock_summary_by_warehouse",
    "get_stock_summary_by_product",
    # Inventory Accounting
    "create_grn_journal_entry",
    "create_sales_issue_journal_entry",
    "create_adjustment_journal_entry",
]
