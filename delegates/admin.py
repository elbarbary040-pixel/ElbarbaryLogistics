from django.contrib import admin

from .models import Delegate, DelegateDailyClose, DelegateTransaction


@admin.register(Delegate)
class DelegateAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return Delegate.all_objects.all()

    list_display = ("name", "phone", "commission_rate", "fixed_deduction", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "phone")


@admin.register(DelegateDailyClose)
class DelegateDailyCloseAdmin(admin.ModelAdmin):
    list_display = ("delegate", "close_date", "closed_at", "closed_by")
    list_filter = ("close_date",)
    date_hierarchy = "close_date"


@admin.register(DelegateTransaction)
class DelegateTransactionAdmin(admin.ModelAdmin):
    list_display = ("delegate", "transaction_date", "tx_type", "direction", "amount", "notes")
    list_filter = ("tx_type", "direction", "transaction_date")
    search_fields = ("delegate__name", "delegate__phone", "notes")
