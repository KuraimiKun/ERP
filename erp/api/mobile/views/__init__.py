"""Employee-mobile view modules.

Re-exports every view callable so URL configs can import from a single
namespace (``from erp.api.mobile.views import mobile_login`` etc.).
"""

from .auth import mobile_login, mobile_logout
from .dashboard import mobile_dashboard
from .profile import mobile_profile, mobile_change_password
from .attendance import mobile_attendance_list, mobile_attendance_scan
from .leaves import mobile_leaves, mobile_leave_cancel
from .payslips import mobile_payslip_list, mobile_payslip_detail
from .tasks import (
    mobile_task_list,
    mobile_task_detail,
    mobile_task_status,
    mobile_task_comment,
)
from .notifications import mobile_notifications, mobile_notifications_read
from .pos import (
    mobile_pos_terminals,
    mobile_pos_session_open,
    mobile_pos_session_detail,
    mobile_pos_session_close,
    mobile_pos_products,
    mobile_pos_categories,
    mobile_pos_customers,
    mobile_pos_payment_methods,
    mobile_pos_create_order,
    mobile_pos_complete_order,
    mobile_pos_receipt,
    mobile_pos_order_history,
    mobile_pos_stats,
)

__all__ = [
    "mobile_login",
    "mobile_logout",
    "mobile_dashboard",
    "mobile_profile",
    "mobile_change_password",
    "mobile_attendance_list",
    "mobile_attendance_scan",
    "mobile_leaves",
    "mobile_leave_cancel",
    "mobile_payslip_list",
    "mobile_payslip_detail",
    "mobile_task_list",
    "mobile_task_detail",
    "mobile_task_status",
    "mobile_task_comment",
    "mobile_notifications",
    "mobile_notifications_read",
    "mobile_pos_terminals",
    "mobile_pos_session_open",
    "mobile_pos_session_detail",
    "mobile_pos_session_close",
    "mobile_pos_products",
    "mobile_pos_categories",
    "mobile_pos_customers",
    "mobile_pos_payment_methods",
    "mobile_pos_create_order",
    "mobile_pos_complete_order",
    "mobile_pos_receipt",
    "mobile_pos_order_history",
    "mobile_pos_stats",
]
