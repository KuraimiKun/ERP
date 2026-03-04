"""
Platform Admin - URL Configuration

All platform admin routes are defined here and included
from the main tenants/urls.py under the 'platform-admin/' prefix.
"""

from django.urls import path

from .views_dashboard import pa_dashboard
from .views_users import (
    pa_user_list, pa_user_detail, pa_user_approve, pa_user_reject,
    pa_user_suspend, pa_user_reactivate, pa_user_delete,
    pa_user_assign_db, pa_bulk_user_action,
)
from .views_servers import (
    pa_server_list, pa_server_detail, pa_server_health_check,
    pa_server_toggle, pa_server_create, pa_server_edit, pa_server_delete,
)
from .views_databases import (
    pa_database_list, pa_database_detail, pa_database_migrate,
    pa_database_test, pa_database_create, pa_database_suspend,
    pa_database_activate, pa_database_delete,
)
from .views_docker import (
    pa_docker_dashboard, pa_docker_stats, pa_docker_stats_api,
    pa_docker_inspect, pa_docker_logs, pa_docker_restart,
    pa_docker_resources, pa_docker_pull_image,
    pa_docker_terminal, pa_docker_terminal_exec,
)
from .views_db_ops import (
    pa_db_performance, pa_db_tables, pa_db_connections,
    pa_db_connections_api, pa_db_kill_connection, pa_db_kill_all_connections,
    pa_db_locks, pa_db_maintenance, pa_db_run_maintenance,
    pa_db_export, pa_db_import, pa_db_clone,
    pa_db_reset_password, pa_server_db_overview,
)
from .views_logs import pa_logs
from .views_activity import pa_activity
from .views_settings import pa_settings, pa_clear_cache, pa_collect_static
from .views_invites import (
    pa_invite_list, pa_invite_detail, pa_invite_create,
    pa_invite_toggle, pa_invite_delete, pa_invite_reset_count,
)
from .views_analytics import (
    pa_analytics, pa_export_users, pa_export_databases, pa_export_logs,
)
from .views_backups import pa_backup_list, pa_backup_database, pa_backup_all
from .views_health import pa_health
from .views_scheduled import (
    pa_scheduled_list, pa_scheduled_create, pa_scheduled_edit,
    pa_scheduled_detail, pa_scheduled_toggle, pa_scheduled_delete,
    pa_scheduled_run_now,
)
from .views_alerts import (
    pa_alert_rules, pa_alert_rule_create, pa_alert_rule_edit,
    pa_alert_rule_toggle, pa_alert_rule_delete,
    pa_alert_list, pa_alert_acknowledge, pa_alert_resolve,
    pa_alert_bulk_action, pa_alert_api,
)
from .views_quotas import (
    pa_quota_list, pa_quota_edit, pa_quota_detail,
    pa_quota_refresh, pa_quota_api,
)
from .views_announcements import (
    pa_announcement_list, pa_announcement_create, pa_announcement_edit,
    pa_announcement_detail, pa_announcement_toggle, pa_announcement_delete,
    pa_announcement_pin,
)
from .views_monitoring import (
    pa_monitoring, pa_monitoring_server, pa_monitoring_api,
)
from .views_tickets import (
    pa_ticket_list, pa_ticket_detail, pa_ticket_reply,
    pa_ticket_assign, pa_ticket_status, pa_ticket_priority,
    pa_ticket_escalate, pa_ticket_close,
    pa_ticket_categories, pa_ticket_category_delete,
    pa_ticket_stats_api,
)


urlpatterns = [
    # ── Dashboard ──
    path('', pa_dashboard, name='pa_dashboard'),

    # ── User Management ──
    path('users/', pa_user_list, name='pa_user_list'),
    path('users/<int:pk>/', pa_user_detail, name='pa_user_detail'),
    path('users/<int:pk>/approve/', pa_user_approve, name='pa_user_approve'),
    path('users/<int:pk>/reject/', pa_user_reject, name='pa_user_reject'),
    path('users/<int:pk>/suspend/', pa_user_suspend, name='pa_user_suspend'),
    path('users/<int:pk>/reactivate/', pa_user_reactivate, name='pa_user_reactivate'),
    path('users/<int:pk>/delete/', pa_user_delete, name='pa_user_delete'),
    path('users/<int:pk>/assign-db/', pa_user_assign_db, name='pa_user_assign_db'),
    path('users/bulk-action/', pa_bulk_user_action, name='pa_bulk_user_action'),

    # ── Server Management ──
    path('servers/', pa_server_list, name='pa_server_list'),
    path('servers/create/', pa_server_create, name='pa_server_create'),
    path('servers/<uuid:pk>/', pa_server_detail, name='pa_server_detail'),
    path('servers/<uuid:pk>/health-check/', pa_server_health_check, name='pa_server_health_check'),
    path('servers/<uuid:pk>/toggle/', pa_server_toggle, name='pa_server_toggle'),
    path('servers/<uuid:pk>/edit/', pa_server_edit, name='pa_server_edit'),
    path('servers/<uuid:pk>/delete/', pa_server_delete, name='pa_server_delete'),
    path('servers/<uuid:pk>/db-overview/', pa_server_db_overview, name='pa_server_db_overview'),

    # ── Database Management ──
    path('databases/', pa_database_list, name='pa_database_list'),
    path('databases/create/', pa_database_create, name='pa_database_create'),
    path('databases/<uuid:pk>/', pa_database_detail, name='pa_database_detail'),
    path('databases/<uuid:pk>/migrate/', pa_database_migrate, name='pa_database_migrate'),
    path('databases/<uuid:pk>/test/', pa_database_test, name='pa_database_test'),
    path('databases/<uuid:pk>/suspend/', pa_database_suspend, name='pa_database_suspend'),
    path('databases/<uuid:pk>/activate/', pa_database_activate, name='pa_database_activate'),
    path('databases/<uuid:pk>/delete/', pa_database_delete, name='pa_database_delete'),

    # ── Database Operations (Enterprise) ──
    path('databases/<uuid:pk>/performance/', pa_db_performance, name='pa_db_performance'),
    path('databases/<uuid:pk>/tables/', pa_db_tables, name='pa_db_tables'),
    path('databases/<uuid:pk>/connections/', pa_db_connections, name='pa_db_connections'),
    path('databases/<uuid:pk>/connections/api/', pa_db_connections_api, name='pa_db_connections_api'),
    path('databases/<uuid:pk>/connections/kill/', pa_db_kill_connection, name='pa_db_kill_connection'),
    path('databases/<uuid:pk>/connections/kill-all/', pa_db_kill_all_connections, name='pa_db_kill_all_connections'),
    path('databases/<uuid:pk>/locks/', pa_db_locks, name='pa_db_locks'),
    path('databases/<uuid:pk>/maintenance/', pa_db_maintenance, name='pa_db_maintenance'),
    path('databases/<uuid:pk>/maintenance/run/', pa_db_run_maintenance, name='pa_db_run_maintenance'),
    path('databases/<uuid:pk>/export/', pa_db_export, name='pa_db_export'),
    path('databases/<uuid:pk>/import/', pa_db_import, name='pa_db_import'),
    path('databases/<uuid:pk>/clone/', pa_db_clone, name='pa_db_clone'),
    path('databases/<uuid:pk>/reset-password/', pa_db_reset_password, name='pa_db_reset_password'),

    # ── Docker Management (Enterprise) ──
    path('docker/', pa_docker_dashboard, name='pa_docker_dashboard'),
    path('docker/<uuid:pk>/stats/', pa_docker_stats, name='pa_docker_stats'),
    path('docker/<uuid:pk>/stats/api/', pa_docker_stats_api, name='pa_docker_stats_api'),
    path('docker/<uuid:pk>/inspect/', pa_docker_inspect, name='pa_docker_inspect'),
    path('docker/<uuid:pk>/logs/', pa_docker_logs, name='pa_docker_logs'),
    path('docker/<uuid:pk>/restart/', pa_docker_restart, name='pa_docker_restart'),
    path('docker/<uuid:pk>/resources/', pa_docker_resources, name='pa_docker_resources'),
    path('docker/<uuid:pk>/terminal/', pa_docker_terminal, name='pa_docker_terminal'),
    path('docker/<uuid:pk>/terminal/exec/', pa_docker_terminal_exec, name='pa_docker_terminal_exec'),
    path('docker/pull-image/', pa_docker_pull_image, name='pa_docker_pull_image'),

    # ── Invite Link Management ──
    path('invites/', pa_invite_list, name='pa_invite_list'),
    path('invites/create/', pa_invite_create, name='pa_invite_create'),
    path('invites/<uuid:pk>/', pa_invite_detail, name='pa_invite_detail'),
    path('invites/<uuid:pk>/toggle/', pa_invite_toggle, name='pa_invite_toggle'),
    path('invites/<uuid:pk>/delete/', pa_invite_delete, name='pa_invite_delete'),
    path('invites/<uuid:pk>/reset-count/', pa_invite_reset_count, name='pa_invite_reset_count'),

    # ── Analytics & Exports ──
    path('analytics/', pa_analytics, name='pa_analytics'),
    path('export/users/', pa_export_users, name='pa_export_users'),
    path('export/databases/', pa_export_databases, name='pa_export_databases'),
    path('export/logs/', pa_export_logs, name='pa_export_logs'),

    # ── Backups ──
    path('backups/', pa_backup_list, name='pa_backup_list'),
    path('backups/all/', pa_backup_all, name='pa_backup_all'),
    path('backups/<uuid:pk>/', pa_backup_database, name='pa_backup_database'),

    # ── System Health ──
    path('health/', pa_health, name='pa_health'),

    # ── Logs & Activity ──
    path('logs/', pa_logs, name='pa_logs'),
    path('activity/', pa_activity, name='pa_activity'),

    # ── Settings ──
    path('settings/', pa_settings, name='pa_settings'),
    path('settings/clear-cache/', pa_clear_cache, name='pa_clear_cache'),
    path('settings/collect-static/', pa_collect_static, name='pa_collect_static'),

    # ── Scheduled Tasks ──
    path('scheduled/', pa_scheduled_list, name='pa_scheduled_list'),
    path('scheduled/create/', pa_scheduled_create, name='pa_scheduled_create'),
    path('scheduled/<uuid:pk>/', pa_scheduled_detail, name='pa_scheduled_detail'),
    path('scheduled/<uuid:pk>/edit/', pa_scheduled_edit, name='pa_scheduled_edit'),
    path('scheduled/<uuid:pk>/toggle/', pa_scheduled_toggle, name='pa_scheduled_toggle'),
    path('scheduled/<uuid:pk>/delete/', pa_scheduled_delete, name='pa_scheduled_delete'),
    path('scheduled/<uuid:pk>/run-now/', pa_scheduled_run_now, name='pa_scheduled_run_now'),

    # ── Alerts & Notifications ──
    path('alerts/rules/', pa_alert_rules, name='pa_alert_rules'),
    path('alerts/rules/create/', pa_alert_rule_create, name='pa_alert_rule_create'),
    path('alerts/rules/<uuid:pk>/edit/', pa_alert_rule_edit, name='pa_alert_rule_edit'),
    path('alerts/rules/<uuid:pk>/toggle/', pa_alert_rule_toggle, name='pa_alert_rule_toggle'),
    path('alerts/rules/<uuid:pk>/delete/', pa_alert_rule_delete, name='pa_alert_rule_delete'),
    path('alerts/', pa_alert_list, name='pa_alert_list'),
    path('alerts/<uuid:pk>/acknowledge/', pa_alert_acknowledge, name='pa_alert_acknowledge'),
    path('alerts/<uuid:pk>/resolve/', pa_alert_resolve, name='pa_alert_resolve'),
    path('alerts/bulk-action/', pa_alert_bulk_action, name='pa_alert_bulk_action'),
    path('alerts/api/', pa_alert_api, name='pa_alert_api'),

    # ── Tenant Quotas ──
    path('quotas/', pa_quota_list, name='pa_quota_list'),
    path('quotas/<uuid:pk>/edit/', pa_quota_edit, name='pa_quota_edit'),
    path('quotas/<uuid:pk>/', pa_quota_detail, name='pa_quota_detail'),
    path('quotas/<uuid:pk>/refresh/', pa_quota_refresh, name='pa_quota_refresh'),
    path('quotas/<uuid:pk>/api/', pa_quota_api, name='pa_quota_api'),

    # ── Announcements ──
    path('announcements/', pa_announcement_list, name='pa_announcement_list'),
    path('announcements/create/', pa_announcement_create, name='pa_announcement_create'),
    path('announcements/<uuid:pk>/', pa_announcement_detail, name='pa_announcement_detail'),
    path('announcements/<uuid:pk>/edit/', pa_announcement_edit, name='pa_announcement_edit'),
    path('announcements/<uuid:pk>/toggle/', pa_announcement_toggle, name='pa_announcement_toggle'),
    path('announcements/<uuid:pk>/delete/', pa_announcement_delete, name='pa_announcement_delete'),
    path('announcements/<uuid:pk>/pin/', pa_announcement_pin, name='pa_announcement_pin'),

    # ── Monitoring History ──
    path('monitoring/', pa_monitoring, name='pa_monitoring'),
    path('monitoring/<uuid:pk>/', pa_monitoring_server, name='pa_monitoring_server'),
    path('monitoring/<uuid:pk>/api/', pa_monitoring_api, name='pa_monitoring_api'),

    # ── Support Tickets ──
    path('tickets/', pa_ticket_list, name='pa_ticket_list'),
    path('tickets/categories/', pa_ticket_categories, name='pa_ticket_categories'),
    path('tickets/categories/<uuid:pk>/delete/', pa_ticket_category_delete, name='pa_ticket_category_delete'),
    path('tickets/stats-api/', pa_ticket_stats_api, name='pa_ticket_stats_api'),
    path('tickets/<uuid:pk>/', pa_ticket_detail, name='pa_ticket_detail'),
    path('tickets/<uuid:pk>/reply/', pa_ticket_reply, name='pa_ticket_reply'),
    path('tickets/<uuid:pk>/assign/', pa_ticket_assign, name='pa_ticket_assign'),
    path('tickets/<uuid:pk>/status/', pa_ticket_status, name='pa_ticket_status'),
    path('tickets/<uuid:pk>/priority/', pa_ticket_priority, name='pa_ticket_priority'),
    path('tickets/<uuid:pk>/escalate/', pa_ticket_escalate, name='pa_ticket_escalate'),
    path('tickets/<uuid:pk>/close/', pa_ticket_close, name='pa_ticket_close'),
]
