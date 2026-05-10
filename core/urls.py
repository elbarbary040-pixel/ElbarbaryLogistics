from django.urls import path

from . import views
from .enterprise_views import (
    approvals_queue,
    approval_decide,
    enterprise_debt_repay,
    enterprise_debts,
    enterprise_hub,
    enterprise_inventory,
    notifications_center,
    offline_help,
    risk_engine_stub,
)

app_name = "core"

urlpatterns = [
    path("reports/profits/", views.profits, name="profits"),
    path("ledger/sync/", views.ledger_summary, name="ledger_sync"),
    path("advanced/hub/", enterprise_hub, name="enterprise_hub"),
    path("advanced/debts/", enterprise_debts, name="enterprise_debts"),
    path("advanced/debts/<int:debt_id>/repay/", enterprise_debt_repay, name="enterprise_debt_repay"),
    path("advanced/inventory/", enterprise_inventory, name="enterprise_inventory"),
    path("advanced/notifications/", notifications_center, name="notifications_center"),
    path("advanced/risk/", risk_engine_stub, name="enterprise_risk"),
    path("advanced/approvals/", approvals_queue, name="enterprise_approvals"),
    path("advanced/approvals/<int:pk>/decide/", approval_decide, name="enterprise_approval_decide"),
    path("advanced/offline/", offline_help, name="offline_help"),
    path("treasury/", views.treasury, name="treasury"),
    path("activity/", views.activity, name="activity"),
    path("devices/", views.devices_list, name="devices"),
    path("settings/", views.settings_site, name="settings"),
    path("external/", views.external_shipments, name="external"),
    path("order-requests/", views.order_requests_list, name="order_requests"),
    path("order-request/new/", views.order_request_new, name="order_request_new"),
    path("chat/", views.chat_center, name="chat"),
    path("audit/", views.audit_list, name="audit"),
    path("users/", views.users_list, name="users"),
    path("users/add/", views.user_add, name="user_add"),
    path("users/<int:user_id>/delete/", views.user_soft_delete, name="user_delete"),
    path("users/<int:user_id>/", views.user_edit, name="user_edit"),
    path("profile/", views.profile, name="profile"),
    path("superadmin/orders-control/", views.superadmin_orders_control, name="superadmin_orders_control"),
    path("superadmin/errors/", views.error_logs_center, name="error_logs_center"),
    path("superadmin/errors/feed/", views.error_logs_feed, name="error_logs_feed"),
    path("superadmin/backups/<str:filename>/", views.db_backup_download, name="db_backup_download"),
]

