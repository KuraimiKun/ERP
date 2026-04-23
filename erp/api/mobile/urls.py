"""
Mobile API URL Configuration.

All endpoints under ``/api/mobile/``.
"""

from django.urls import path

from . import views

urlpatterns = [
    # Auth
    path('auth/login/', views.mobile_login, name='mobile_login'),
    path('auth/logout/', views.mobile_logout, name='mobile_logout'),

    # Dashboard
    path('dashboard/', views.mobile_dashboard, name='mobile_dashboard'),

    # Profile
    path('profile/', views.mobile_profile, name='mobile_profile'),
    path('password/', views.mobile_change_password, name='mobile_change_password'),

    # Attendance
    path('attendance/', views.mobile_attendance_list, name='mobile_attendance_list'),
    path('attendance/scan/', views.mobile_attendance_scan, name='mobile_attendance_scan'),

    # Leaves
    path('leaves/', views.mobile_leaves, name='mobile_leaves'),
    path('leaves/<int:pk>/cancel/', views.mobile_leave_cancel, name='mobile_leave_cancel'),

    # Payslips
    path('payslips/', views.mobile_payslip_list, name='mobile_payslip_list'),
    path('payslips/<int:pk>/', views.mobile_payslip_detail, name='mobile_payslip_detail'),

    # Tasks
    path('tasks/', views.mobile_task_list, name='mobile_task_list'),
    path('tasks/<int:pk>/', views.mobile_task_detail, name='mobile_task_detail'),
    path('tasks/<int:pk>/status/', views.mobile_task_status, name='mobile_task_status'),
    path('tasks/<int:pk>/comment/', views.mobile_task_comment, name='mobile_task_comment'),

    # Notifications
    path('notifications/', views.mobile_notifications, name='mobile_notifications'),
    path('notifications/read/', views.mobile_notifications_read, name='mobile_notifications_read'),

    # POS
    path('pos/terminals/', views.mobile_pos_terminals, name='mobile_pos_terminals'),
    path('pos/sessions/open/', views.mobile_pos_session_open, name='mobile_pos_session_open'),
    path('pos/sessions/<int:pk>/', views.mobile_pos_session_detail, name='mobile_pos_session_detail'),
    path('pos/sessions/<int:pk>/close/', views.mobile_pos_session_close, name='mobile_pos_session_close'),
    path('pos/products/', views.mobile_pos_products, name='mobile_pos_products'),
    path('pos/categories/', views.mobile_pos_categories, name='mobile_pos_categories'),
    path('pos/customers/', views.mobile_pos_customers, name='mobile_pos_customers'),
    path('pos/payment-methods/', views.mobile_pos_payment_methods, name='mobile_pos_payment_methods'),
    path('pos/orders/create/', views.mobile_pos_create_order, name='mobile_pos_create_order'),
    path('pos/orders/complete/', views.mobile_pos_complete_order, name='mobile_pos_complete_order'),
    path('pos/orders/<int:pk>/receipt/', views.mobile_pos_receipt, name='mobile_pos_receipt'),
    path('pos/orders/history/<int:session_id>/', views.mobile_pos_order_history, name='mobile_pos_order_history'),
    path('pos/stats/', views.mobile_pos_stats, name='mobile_pos_stats'),
]
