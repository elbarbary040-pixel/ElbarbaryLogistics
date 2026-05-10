from django.conf import settings
from django.db import models
from django.utils import timezone


class DelegateQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class DelegateManager(models.Manager.from_queryset(DelegateQuerySet)):
    def get_queryset(self):
        return super().get_queryset().alive()


class Delegate(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    linked_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delegate_profile",
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.75)
    fixed_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delegates_soft_deleted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DelegateManager()
    all_objects = models.Manager()

    class Meta:
        indexes = [models.Index(fields=["name"], name="delegate_name_idx")]

    def __str__(self) -> str:
        return self.name

    def soft_delete(self, user):
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.is_active = False
        self.save(update_fields=["deleted_at", "deleted_by", "is_active", "updated_at"])


class DelegateTransactionType(models.TextChoices):
    ADVANCE = "advance", "عهدة"
    TRANSFER = "transfer", "تحويل"
    DEPOSIT = "deposit", "توريد"


class TransactionDirection(models.TextChoices):
    IN = "in", "داخل"
    OUT = "out", "خارج"


class DelegateTransaction(models.Model):
    delegate = models.ForeignKey(Delegate, on_delete=models.CASCADE, related_name="delegate_transactions")
    transaction_date = models.DateField(default=timezone.localdate)
    tx_type = models.CharField(max_length=20, choices=DelegateTransactionType.choices)
    direction = models.CharField(max_length=10, choices=TransactionDirection.choices, default=TransactionDirection.IN)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        indexes = [
            models.Index(fields=["transaction_date"], name="delegatetx_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.delegate.name} - {self.amount}"


class DelegateDailyClose(models.Model):
    """
    تصفية يوم المندوب: زر «تم التوريد» يسجل إغلاق اليوم دون حذف الأوردرات.
    unique_together يمنع إغلاق نفس اليوم مرتين لنفس المندوب.
    """

    delegate = models.ForeignKey(
        Delegate,
        on_delete=models.CASCADE,
        related_name="daily_closes",
    )
    close_date = models.DateField(db_index=True)
    closed_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-close_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["delegate", "close_date"],
                name="delegate_daily_close_unique",
            )
        ]
        verbose_name = "توريد يومي (مندوب)"
        verbose_name_plural = "توريدات يومية"

    def __str__(self) -> str:
        return f"{self.delegate} — {self.close_date}"


class DelegateSettlementItem(models.Model):
    class ItemKind(models.TextChoices):
        ACCOUNTED = "accounted", "حاسب أنت"
        ADVANCE = "advance", "عهدة"
        OTHER = "other", "أخرى"

    delegate = models.ForeignKey(
        Delegate,
        on_delete=models.CASCADE,
        related_name="settlement_items",
    )
    item_date = models.DateField(default=timezone.localdate, db_index=True)
    title = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    kind = models.CharField(max_length=20, choices=ItemKind.choices, default=ItemKind.OTHER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-item_date", "-id"]

    @property
    def total(self):
        return (self.quantity or 0) * (self.unit_price or 0)

    def __str__(self) -> str:
        return f"{self.delegate} - {self.title}"


class DelegateDailyMetric(models.Model):
    delegate = models.ForeignKey(
        Delegate,
        on_delete=models.CASCADE,
        related_name="daily_metrics",
    )
    metric_date = models.DateField(db_index=True)
    advance_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    work_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cash_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    net_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["delegate", "metric_date"],
                name="delegate_daily_metric_unique",
            )
        ]
        ordering = ["-metric_date", "-id"]

    def __str__(self) -> str:
        return f"{self.delegate} {self.metric_date}"
