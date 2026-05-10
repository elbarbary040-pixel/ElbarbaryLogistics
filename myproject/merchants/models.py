from django.db import models
from django.utils import timezone
from django.conf import settings


class MerchantQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class MerchantManager(models.Manager.from_queryset(MerchantQuerySet)):
    def get_queryset(self):
        return super().get_queryset().alive()


class Merchant(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    brand_name = models.CharField(max_length=255, blank=True)
    linked_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merchant_profile",
    )
    is_external = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="merchants_soft_deleted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MerchantManager()
    all_objects = models.Manager()

    class Meta:
        indexes = [models.Index(fields=["name"], name="merchant_name_idx")]

    def __str__(self) -> str:
        return self.name

    def soft_delete(self, user):
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.is_active = False
        self.save(update_fields=["deleted_at", "deleted_by", "is_active", "updated_at"])


class PaymentDirection(models.TextChoices):
    IN = "in", "قبض من التاجر"
    OUT = "out", "صرف للتاجر"


class MerchantPayment(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="payments")
    payment_date = models.DateField(default=timezone.localdate)
    direction = models.CharField(max_length=10, choices=PaymentDirection.choices, default=PaymentDirection.IN)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        indexes = [
            models.Index(fields=["payment_date"], name="merchantpay_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.merchant.name} - {self.amount}"
