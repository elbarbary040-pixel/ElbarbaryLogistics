from django.contrib import admin

from .models import (
    AppErrorLog,
    AuditLog,
    Branch,
    ChatMessage,
    ChatThread,
    ClientSession,
    CommissionRule,
    Debt,
    DebtRepayment,
    ExternalShipmentBatch,
    ExternalShipmentRow,
    InventoryMovement,
    LedgerEntry,
    MerchantStockItem,
    NotificationEvent,
    OrderRequest,
    SensitiveApprovalRequest,
    SiteAppearance,
    TreasuryAccount,
    TreasuryEntry,
    UserProfile,
)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "action",
        "model_name",
        "object_id",
        "object_repr",
        "message",
    )
    list_filter = ("action", "model_name")
    search_fields = ("object_id", "object_repr", "message", "path", "user__username")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone", "updated_at")
    list_filter = ("role",)
    search_fields = ("user__username", "phone")


@admin.register(SiteAppearance)
class SiteAppearanceAdmin(admin.ModelAdmin):
    list_display = ("pk", "primary_color", "accent_color", "updated_at")


@admin.register(TreasuryAccount)
class TreasuryAccountAdmin(admin.ModelAdmin):
    list_display = ("kind", "label", "is_active")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "entry_type",
        "amount",
        "from_entity",
        "to_entity",
        "order_id",
        "branch_id",
    )
    list_filter = ("entry_type", "branch")
    search_fields = ("from_entity", "to_entity", "note", "idempotency_key")
    readonly_fields = ("idempotency_key",)


@admin.register(TreasuryEntry)
class TreasuryEntryAdmin(admin.ModelAdmin):
    list_display = ("entry_date", "account", "amount", "direction", "reason", "order_id")
    list_filter = ("direction", "reason", "account")
    date_hierarchy = "entry_date"


@admin.register(ExternalShipmentBatch)
class ExternalShipmentBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "source_name", "imported_at", "imported_by")


@admin.register(ExternalShipmentRow)
class ExternalShipmentRowAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "profit_amount", "created_at")


@admin.register(ClientSession)
class ClientSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "ip_address", "device_label", "last_seen_at")
    list_filter = ("user",)


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "participant", "updated_at")
    search_fields = ("participant__username",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at")
    search_fields = ("body", "sender__username")


@admin.register(OrderRequest)
class OrderRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "requester", "merchant", "assigned_delegate", "status", "created_at")
    list_filter = ("status",)


@admin.register(AppErrorLog)
class AppErrorLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "path", "error_type")
    search_fields = ("path", "error_type", "message")


@admin.register(CommissionRule)
class CommissionRuleAdmin(admin.ModelAdmin):
    list_display = ("priority", "is_active", "merchant", "delegate", "branch", "commission_rate", "fixed_addon")
    list_filter = ("is_active", "branch")
    search_fields = ("note",)


@admin.register(MerchantStockItem)
class MerchantStockItemAdmin(admin.ModelAdmin):
    list_display = ("label", "merchant", "sku_code", "quantity_on_hand", "updated_at")
    list_filter = ("merchant",)
    search_fields = ("label", "sku_code")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "item", "delta", "reason", "order")
    list_filter = ("reason",)
    readonly_fields = ("created_at",)


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ("title", "amount_total", "status", "merchant", "delegate", "order", "created_at")
    list_filter = ("status",)


@admin.register(DebtRepayment)
class DebtRepaymentAdmin(admin.ModelAdmin):
    list_display = ("debt", "amount", "payment_date", "created_at")


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "channel", "title", "read_at")
    list_filter = ("channel",)
    search_fields = ("title", "body")


@admin.register(SensitiveApprovalRequest)
class SensitiveApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action_key", "summary", "status", "submitted_by", "reviewed_by")
    list_filter = ("status", "action_key")
    search_fields = ("summary", "action_key")
