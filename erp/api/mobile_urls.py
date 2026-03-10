"""
Mobile API URL Configuration

All endpoints under /api/mobile/
"""

from django.urls import path
from . import mobile_views

urlpatterns = [
    # Auth
    path('auth/login/', mobile_views.mobile_login, name='mobile_login'),
    path('auth/logout/', mobile_views.mobile_logout, name='mobile_logout'),

    # Dashboard
    path('dashboard/', mobile_views.mobile_dashboard, name='mobile_dashboard'),

    # Profile
    path('profile/', mobile_views.mobile_profile, name='mobile_profile'),
    path('password/', mobile_views.mobile_change_password, name='mobile_change_password'),

    # Attendance
    path('attendance/', mobile_views.mobile_attendance_list, name='mobile_attendance_list'),
    path('attendance/scan/', mobile_views.mobile_attendance_scan, name='mobile_attendance_scan'),

    # Leaves
    path('leaves/', mobile_views.mobile_leaves, name='mobile_leaves'),
    path('leaves/<int:pk>/cancel/', mobile_views.mobile_leave_cancel, name='mobile_leave_cancel'),

    # Payslips
    path('payslips/', mobile_views.mobile_payslip_list, name='mobile_payslip_list'),
    path('payslips/<int:pk>/', mobile_views.mobile_payslip_detail, name='mobile_payslip_detail'),

    # Tasks
    path('tasks/', mobile_views.mobile_task_list, name='mobile_task_list'),
    path('tasks/<int:pk>/', mobile_views.mobile_task_detail, name='mobile_task_detail'),
    path('tasks/<int:pk>/status/', mobile_views.mobile_task_status, name='mobile_task_status'),
    path('tasks/<int:pk>/comment/', mobile_views.mobile_task_comment, name='mobile_task_comment'),

    # Notifications
    path('notifications/', mobile_views.mobile_notifications, name='mobile_notifications'),
    path('notifications/read/', mobile_views.mobile_notifications_read, name='mobile_notifications_read'),

    # POS
    path('pos/terminals/', mobile_views.mobile_pos_terminals, name='mobile_pos_terminals'),
    path('pos/sessions/open/', mobile_views.mobile_pos_session_open, name='mobile_pos_session_open'),
    path('pos/sessions/<int:pk>/', mobile_views.mobile_pos_session_detail, name='mobile_pos_session_detail'),
    path('pos/sessions/<int:pk>/close/', mobile_views.mobile_pos_session_close, name='mobile_pos_session_close'),
    path('pos/products/', mobile_views.mobile_pos_products, name='mobile_pos_products'),
    path('pos/categories/', mobile_views.mobile_pos_categories, name='mobile_pos_categories'),
    path('pos/customers/', mobile_views.mobile_pos_customers, name='mobile_pos_customers'),
    path('pos/payment-methods/', mobile_views.mobile_pos_payment_methods, name='mobile_pos_payment_methods'),
    path('pos/orders/create/', mobile_views.mobile_pos_create_order, name='mobile_pos_create_order'),
    path('pos/orders/complete/', mobile_views.mobile_pos_complete_order, name='mobile_pos_complete_order'),
    path('pos/orders/<int:pk>/receipt/', mobile_views.mobile_pos_receipt, name='mobile_pos_receipt'),
    path('pos/orders/history/<int:session_id>/', mobile_views.mobile_pos_order_history, name='mobile_pos_order_history'),
    path('pos/stats/', mobile_views.mobile_pos_stats, name='mobile_pos_stats'),
]
