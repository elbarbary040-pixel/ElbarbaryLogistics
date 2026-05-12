from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
import random


class OrderStatus(models.TextChoices):
    """حالات تشغيلية لتصفية ولوحة التحكم؛ الحالتان التاليتان قبلية للتوافق مع البيانات المخزَّنة."""

    DELIVERED = "delivered", "تم التسليم"
    IN_TRANSIT = "in_transit", "في الطريق"
    ACCOUNTED = "accounted", "حاسب أنت"
    PARTIALLY_DELIVERED = "partially_delivered", "تسليم جزئي"
    PARTIALLY_DELIVERED_WITH_RETURN = "partially_delivered_with_return", "تسليم جزئي مع مرتجع"
    RETURNED = "returned", "مرتجع"
    POSTPONED = "postponed", "مؤجل"
    PAID_TO_COMPANY = "paid_to_company", "مدفوع للشركة شامل الشحن"

def generate_waybill():
    # ضمان عدم تكرار رقم البوليصة حتى مع الضغط العالي.
    from django.apps import apps

    OrderModel = apps.get_model("orders", "Order")
    for _ in range(100):
        candidate = f"BRB{random.randint(100000, 999999)}"
        if not OrderModel.objects.filter(waybill_number=candidate).exists():
            return candidate
    return f"BRB{random.randint(100000000, 999999999)}"


waybill_validator = RegexValidator(
    regex=r"^BRB\d+$",
    message="رقم البوليصة لازم يبدأ بـ BRB وبعده أرقام فقط. مثال: BRB12345",
)


class OrderQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class OrderManager(models.Manager.from_queryset(OrderQuerySet)):
    def get_queryset(self):
        return super().get_queryset().alive()


class Order(models.Model):
    """
    الشحنة الأساسية.
    - البوليصة + التاجر + المندوب هم الأهم للبحث والتقارير.
    - owned_by: لاحقًا المستخدم العادي يشوف أوردراته فقط (null = قديم / للجميع حسب الصلاحية).
    - منطق المحاسبة عند تغيير الحالة (عهدة، عمولة، خزنة) يُنفَّذ في الخطوات القادمة عبر
      إشارات أو خدمة تسوية؛ هنا نجهز الحقول والعلاقات فقط.
    """

    waybill_number = models.CharField(
        max_length=50,
        unique=True,
        validators=[waybill_validator],
        blank=True,
    )
    external_waybill = models.CharField(max_length=50, blank=True, null=True)
    order_date = models.DateField(default=timezone.localdate, db_index=True)

    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )
    delegate = models.ForeignKey(
        "delegates.Delegate",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )
    branch = models.ForeignKey(
        "core.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_address = models.CharField(max_length=500, blank=True)

    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=48,
        choices=OrderStatus.choices,
        default=OrderStatus.IN_TRANSIT,
        db_index=True,
    )

    notes = models.TextField(blank=True)

    owned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_orders",
        verbose_name="مسؤول الأوردر",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders_updated",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders_soft_deleted",
    )

    objects = OrderManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-order_date", "-id"]
        indexes = [
            models.Index(fields=["-order_date", "status"], name="order_date_status_idx"),
        ]

    def __str__(self):
        return self.waybill_number or "بدون رقم"

    def soft_delete(self, user):
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=["deleted_at", "deleted_by", "updated_at"])

    def clean(self):
        if self.waybill_number and not self.waybill_number.upper().startswith("BRB"):
            raise ValidationError(
                {"waybill_number": "رقم البوليصة لازم يبدأ بـ BRB"}
            )

    def save(self, *args, **kwargs):
        if not self.waybill_number:
            self.waybill_number = generate_waybill()
        self.full_clean()
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    """سجل تغيير حالة الأوردر (مهم للتصفية اليومية والمراجعة)."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_status = models.CharField(max_length=48, blank=True)
    new_status = models.CharField(max_length=48)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-changed_at", "-id"]
        indexes = [
            models.Index(fields=["order", "-changed_at"], name="ordstat_hist_order_idx"),
        ]

    def __str__(self) -> str:
        oid = getattr(self, "order_id", None)
        return f"{oid}: {self.old_status} → {self.new_status}"
# ========================
# 💰 حسابات التاجر
# ========================

class MerchantTransaction(models.Model):
    TRANSACTION_TYPE = (
        ("add", "إضافة"),
        ("subtract", "خصم"),
    )

    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merchant_transactions"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)

    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.merchant.name} - {self.amount}"


# ========================
# 💰 حسابات المندوب
# ========================

class DelegateTransaction(models.Model):
    TRANSACTION_TYPE = (
        ("add", "إضافة"),
        ("subtract", "خصم"),
    )

    delegate = models.ForeignKey(
    "delegates.Delegate",
    on_delete=models.CASCADE,
    related_name="order_transactions"
)

    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delegate_transactions"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)

    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.delegate.name} - {self.amount}"