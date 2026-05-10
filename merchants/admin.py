from django.contrib import admin

from .models import Merchant, MerchantPayment


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return Merchant.all_objects.all()

    list_display = ("name", "phone", "brand_name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "phone", "brand_name")


@admin.register(MerchantPayment)
class MerchantPaymentAdmin(admin.ModelAdmin):
    list_display = ("merchant", "payment_date", "direction", "amount", "notes")
    list_filter = ("direction", "payment_date")
    search_fields = ("merchant__name", "merchant__phone", "notes")
