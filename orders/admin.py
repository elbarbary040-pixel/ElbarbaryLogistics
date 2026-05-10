from django.contrib import admin

from .models import Order, OrderStatusHistory


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_at", "changed_by")


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "old_status", "new_status", "changed_at", "changed_by")
    list_filter = ("new_status",)
    date_hierarchy = "changed_at"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return Order.all_objects.select_related("merchant", "delegate")

    list_display = (
        "waybill_number",
        "order_date",
        "merchant",
        "delegate",
        "status",
        "product_price",
        "shipping_price",
    )
    list_filter = ("status", "order_date")
    inlines = [OrderStatusHistoryInline]
    search_fields = (
        "waybill_number",
        "customer_name",
        "customer_phone",
        "customer_address",
        "merchant__name",
        "merchant__phone",
        "delegate__name",
        "delegate__phone",
    )
