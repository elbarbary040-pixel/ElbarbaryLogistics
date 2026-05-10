"""
نماذج مشتركة: المستخدم والصلاحيات، سجل العمليات، الخزنة، الشحنات الخارجية، الأجهزة.

الفكرة باختصار:
- UserProfile: نوع المستخدم (مدير عام / مسؤول / مستخدم) مربوط بحساب Django.
- AuditLog: تسجيل من عمل إيه على أي سجل (موجود مسبقًا، تم توسيعه).
- SiteAppearance: إعدادات شكل البرنامج (ألوان + لوجو) — صف واحد فقط.
- TreasuryAccount / TreasuryEntry: خزنة داخلية وخارجية + حركات مالية مرتبطة بالأوردر أو يدويًا.
- ExternalShipmentBatch / Row: استيراد من شركات خارجية مع أعمدة ديناميكية (JSON).
- ClientSession: تتبع أجهزة/جلسات (للتطوير لاحقًا مع Middleware).
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone


# ---------------------------------------------------------------------------
# سجل التدقيق (Log)
# ---------------------------------------------------------------------------
class AuditAction(models.TextChoices):
    CREATE = "create", "إنشاء"
    UPDATE = "update", "تعديل"
    DELETE = "delete", "حذف"
    OTHER = "other", "أخرى"


class AuditLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(
        max_length=20,
        choices=AuditAction.choices,
        default=AuditAction.OTHER,
    )
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    message = models.CharField(max_length=255, blank=True)
    path = models.CharField(max_length=255, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"], name="audit_created_idx"),
            models.Index(fields=["model_name"], name="audit_model_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.created_at} - {self.model_name} - {self.action}"


# ---------------------------------------------------------------------------
# الصلاحيات (مربوطة بـ User الافتراضي في Django)
# ---------------------------------------------------------------------------
class UserRole(models.TextChoices):
    SUPER_ADMIN = "super_admin", "مدير عام"
    ADMIN = "admin", "مسؤول"
    USER = "user", "مستخدم"
    MERCHANT = "merchant", "تاجر"
    DELEGATE = "delegate", "مندوب"


class UserProfile(models.Model):
    """
    كل مستخدم ليه ملف واحد يحدد دوره.
    لاحقًا في الـ Views: User يشوف أوردراته فقط، Admin يدير المستخدمين، إلخ.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.USER,
    )
    phone = models.CharField(max_length=20, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ملف مستخدم"
        verbose_name_plural = "ملفات المستخدمين"

    def __str__(self) -> str:
        role_label = dict(UserRole.choices).get(self.role, self.role)
        return f"{self.user} ({role_label})"


# ---------------------------------------------------------------------------
# إعدادات الواجهة (لوجو + ألوان) — Super Admin يعدل اللوجو
# ---------------------------------------------------------------------------
class SiteAppearance(models.Model):
    """
    نخزن صف واحد فقط (pk=1): ألوان عامة + لوجو الشركة.
    """

    logo = models.ImageField(upload_to="branding/", blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#0d6efd")
    accent_color = models.CharField(max_length=7, default="#198754")
    sidebar_color = models.CharField(max_length=7, default="#2f3542")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "مظهر النظام"
        verbose_name_plural = "مظهر النظام"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> tuple[int, dict[str, int]]:
        """منع حذف صف الإعدادات؛ نفس سلوك Django من حيث نوع القيمة المُرجَعة."""
        return (0, {})

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return "إعدادات المظهر"


# ---------------------------------------------------------------------------
# الخزنة (داخلي / خارجي) + حركات
# ---------------------------------------------------------------------------
class TreasuryKind(models.TextChoices):
    INTERNAL = "internal", "خزنة داخلية"
    EXTERNAL = "external", "خزنة خارجية"


class TreasuryAccount(models.Model):
    """حسابان ثابتان: داخلي وخارجي (يتم إنشاؤهم مرة بالهجرة أو أمر إداري)."""

    kind = models.CharField(
        max_length=20,
        choices=TreasuryKind.choices,
        unique=True,
    )
    label = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "حساب خزنة"
        verbose_name_plural = "حسابات الخزنة"

    def __str__(self) -> str:
        return str(dict(TreasuryKind.choices).get(self.kind, self.kind))


class TreasuryDirection(models.TextChoices):
    IN = "in", "وارد"
    OUT = "out", "منصرف"


class TreasuryReason(models.TextChoices):
    """أسباب الحركة — نوسعها لما نربط منطق الأوردر بالمحاسبة."""

    ORDER_DELIVERED_PROFIT = "order_delivered_profit", "ربح من تسليم أوردر"
    ORDER_ACCOUNTED = "order_accounted", "تسوية حاسب أنت"
    MANUAL = "manual", "يدوي"
    PROFIT_INTERNAL = "profit_internal", "أرباح داخلية"
    PROFIT_EXTERNAL = "profit_external", "أرباح خارجية"
    ADJUSTMENT = "adjustment", "تسوية / تعديل"
    OTHER = "other", "أخرى"


class TreasuryEntry(models.Model):
    """
    كل سطر = حركة مالية في تاريخ معيّن.
    amount دائمًا موجب؛ الاتجاه in/out يحدد هل الفلوس دخلت الخزنة ولا طلعت.
    """

    account = models.ForeignKey(
        TreasuryAccount,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    entry_date = models.DateField(default=timezone.localdate, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    direction = models.CharField(
        max_length=3,
        choices=TreasuryDirection.choices,
        default=TreasuryDirection.IN,
    )
    reason = models.CharField(
        max_length=40,
        choices=TreasuryReason.choices,
        default=TreasuryReason.OTHER,
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="treasury_entries",
    )
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entry_date", "-id"]
        indexes = [
            models.Index(fields=["entry_date", "account"], name="treasury_date_acc_idx"),
        ]
        verbose_name = "حركة خزنة"
        verbose_name_plural = "حركات الخزنة"

    def __str__(self) -> str:
        reason_label = dict(TreasuryReason.choices).get(self.reason, self.reason)
        return f"{self.entry_date} {reason_label} {self.amount}"


# ---------------------------------------------------------------------------
# شحنات خارجية (استيراد Excel — أعمدة ديناميكية)
# ---------------------------------------------------------------------------
class ExternalShipmentBatch(models.Model):
    imported_at = models.DateTimeField(auto_now_add=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    source_name = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-imported_at", "-id"]
        verbose_name = "دفعة شحن خارجي"
        verbose_name_plural = "دفعات الشحن الخارجي"

    def __str__(self) -> str:
        return self.source_name or f"دفعة #{self.pk}"


class ExternalShipmentRow(models.Model):
    batch = models.ForeignKey(
        ExternalShipmentBatch,
        on_delete=models.CASCADE,
        related_name="rows",
    )
    row_data = models.JSONField(default=dict)
    profit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["batch"], name="extrow_batch_idx")]

    def __str__(self) -> str:
        bid = getattr(self, "batch_id", None)
        return f"صف في {bid}" if bid is not None else "صف شحن خارجي"


# ---------------------------------------------------------------------------
# أجهزة / جلسات (أساس لصفحة "الأجهزة المتصلة")
# ---------------------------------------------------------------------------
class ClientSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_sessions",
    )
    device_label = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [
            models.Index(fields=["user", "-last_seen_at"], name="clientsess_user_seen"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.last_seen_at}"


class ChatThread(models.Model):
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_threads",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["participant", "-updated_at"], name="chat_participant_idx")]

    def __str__(self) -> str:
        return f"Chat with {self.participant}"


class ChatMessage(models.Model):
    thread = models.ForeignKey(
        ChatThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_chat_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["thread", "created_at"], name="chat_msg_thread_idx")]

    def __str__(self) -> str:
        return f"msg:{self.pk} thread:{self.thread_id}"


class OrderRequestStatus(models.TextChoices):
    PENDING = "pending", "قيد المراجعة"
    APPROVED = "approved", "مقبول"
    REJECTED = "rejected", "مرفوض"


class OrderRequest(models.Model):
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="order_requests",
    )
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_requests",
    )
    assigned_delegate = models.ForeignKey(
        "delegates.Delegate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_order_requests",
    )
    created_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_requests",
    )
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_address = models.CharField(max_length=500, blank=True)
    product_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=OrderRequestStatus.choices,
        default=OrderRequestStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "-created_at"], name="orderreq_status_idx")]

    def __str__(self) -> str:
        return f"طلب #{self.pk} - {self.customer_name}"


# ---------------------------------------------------------------------------
# فروع العمل — عزل تشغيلي ومحاسبي اختياري (يربط الطلب بدون تحقير السجلات القديمة).
# ---------------------------------------------------------------------------
class Branch(models.Model):
    name = models.CharField(max_length=150, db_index=True)
    code = models.SlugField(max_length=40, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "فرع"
        verbose_name_plural = "فروع"

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# دفتر حركة موحد (مزدوج تجاهياً بين من وتجاه) — لا يمس الجداول المالية القديمة.
# ---------------------------------------------------------------------------
class LedgerEntry(models.Model):
    """
    كل سجل يمثل حركة واحدة بين كيانَين؛ يمكن ربطه بالطلب والفرع.
    idempotency_key يمنع تكرار نفس الآثار عند إعادة التشغيل أو التصفية المحاسبية.
    """

    class EntryType(models.TextChoices):
        COLLECTION = "collection", "تحصيل"
        SHIPPING_INCOME = "shipping_income", "دخل الشحن"
        COURIER_COMMISSION = "courier_commission", "عمولة مندوب"
        COURIER_SALARY = "courier_salary", "مرتب مندوب"
        HANDOVER = "handover", "توريد (مندوب → شركة)"
        CASH_OUT = "cash_out", "صرف (شركة → مندوب)"
        TRANSFER = "transfer", "تحويل (مندوب ↔ مندوب)"
        MERCHANT_ADVANCE = "merchant_advance", "عربون تاجر"
        MERCHANT_PAYMENT = "merchant_payment", "حركة حساب تاجر"
        ADJUSTMENT = "adjustment", "تعديل / تسوية"
        INVENTORY_MOVEMENT = "inventory_movement", "مخزون / مرتجع"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    from_entity = models.CharField(max_length=128, db_index=True)
    to_entity = models.CharField(max_length=128, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    entry_type = models.CharField(
        max_length=32,
        choices=EntryType.choices,
        db_index=True,
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    note = models.CharField(max_length=500, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["order", "entry_type"], name="ledger_order_type_idx"),
            models.Index(fields=["branch", "-created_at"], name="ledger_branch_created_idx"),
        ]
        verbose_name = "قيد دفتر"
        verbose_name_plural = "قيود الدفتر"

    def __str__(self) -> str:
        return f"{self.entry_type} {self.amount}"


# ---------------------------------------------------------------------------
# قواعد عمولة تشغيلية — أولاً الأعلى أولوية ومطابق أدق لمزيج (تاجر/مندوب/فرع).
# ---------------------------------------------------------------------------
class CommissionRule(models.Model):
    priority = models.PositiveIntegerField(default=100, db_index=True)
    is_active = models.BooleanField(default=True)
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="commission_rules",
    )
    delegate = models.ForeignKey(
        "delegates.Delegate",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="commission_rules",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="commission_rules",
    )
    commission_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        help_text="من سعر الشحن (مثل ٠٫٧٥ = ٧٥٪)",
    )
    fixed_addon = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="يُستخدم لاستثناءات بسيطة لكل طلب مطابق")
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-priority", "-id"]
        verbose_name = "قاعدة عمولة"
        verbose_name_plural = "قواعد العمولة"

    def __str__(self) -> str:
        return f"@{self.priority} {self.commission_rate}"


# ---------------------------------------------------------------------------
# مخزون مبسّط لكل تاجر (أصناف وكميات) + حركات.
# ---------------------------------------------------------------------------
class MerchantStockItem(models.Model):
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="stock_items",
    )
    sku_code = models.CharField(max_length=60, blank=True, db_index=True)
    label = models.CharField(max_length=200)
    quantity_on_hand = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["merchant_id", "label"]
        indexes = [
            models.Index(fields=["merchant", "label"], name="stk_merchant_label_idx"),
            models.Index(fields=["merchant", "sku_code"], name="stk_merchant_sku_idx"),
        ]
        verbose_name = "صنف مخزون"
        verbose_name_plural = "أصناف المخزون"

    def __str__(self) -> str:
        return f"{self.merchant} — {self.label}"


class InventoryMovement(models.Model):
    class Reason(models.TextChoices):
        RECEIPT = "receipt", "استلام مخزون"
        RETURN_ORDER = "return_order", "مرتجع شحنة"
        ADJUST = "adjust", "تسوية أو تعديل"
        TRANSFER_OUT = "transfer_out", "صادر داخلي"
        OTHER = "other", "أخرى"

    item = models.ForeignKey(
        MerchantStockItem,
        on_delete=models.CASCADE,
        related_name="movements",
    )
    delta = models.IntegerField(help_text="موجب زيادة، سالب نقصان")
    reason = models.CharField(max_length=32, choices=Reason.choices, default=Reason.ADJUST)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item", "-created_at"], name="invmov_item_created_idx"),
        ]
        verbose_name = "حركة مخزون"
        verbose_name_plural = "حركات مخزون"

    def __str__(self) -> str:
        return f"{self.item_id} Δ{self.delta}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            MerchantStockItem.objects.filter(pk=self.item_id).update(
                quantity_on_hand=F("quantity_on_hand") + self.delta,
            )


# ---------------------------------------------------------------------------
# ديون مستقلّة لمتابعة كيان واحد مستحق للشركة أو العكس مع سجل تحصيل.
# ---------------------------------------------------------------------------
class Debt(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "مفتوح"
        PARTIAL = "partial", "جزئي"
        CLOSED = "closed", "مسدَّد أو مغلق"

    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debts",
    )
    delegate = models.ForeignKey(
        "delegates.Delegate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debts",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debts",
    )
    title = models.CharField(max_length=200)
    amount_total = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status"], name="debt_status_idx")]
        verbose_name = "سجل مديونية"
        verbose_name_plural = "الديون والمستحقّات"

    def clean(self):
        has_m = bool(self.merchant_id)
        has_d = bool(self.delegate_id)
        if has_m == has_d:
            raise ValidationError("اختَر طرفاً واحداً: تاجر أو مندوب (وليس كلاهما وليس فارغاً).")

    def __str__(self) -> str:
        party = ""
        if self.merchant_id:
            party = str(self.merchant)
        elif self.delegate_id:
            party = str(self.delegate)
        return f"{self.title} — {party}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def refresh_payment_status(self) -> None:
        paid_raw = self.repayments.aggregate(s=Sum("amount"))["s"]
        paid = Decimal(paid_raw or "0").quantize(Decimal("0.01"))
        total = Decimal(self.amount_total or "0").quantize(Decimal("0.01"))
        if paid <= 0:
            st = self.Status.OPEN
        elif paid < total:
            st = self.Status.PARTIAL
        else:
            st = self.Status.CLOSED
        type(self).objects.filter(pk=self.pk).update(status=st)
        self.status = st


class DebtRepayment(models.Model):
    debt = models.ForeignKey(Debt, on_delete=models.CASCADE, related_name="repayments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField(default=timezone.localdate)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        verbose_name = "سداد دَين"
        verbose_name_plural = "سدادات الديون"


# ---------------------------------------------------------------------------
# إشعار داخل التطبيق (قناة واحدة الآن؛ جاهز لتوسعة واتساب/بريد).
# ---------------------------------------------------------------------------
class NotificationEvent(models.Model):
    class Channel(models.TextChoices):
        IN_APP = "in_app", "عرض في النظام"
        WA_PENDING = "wa_pending", "بانتظار واتساب"
        MAIL_PENDING = "mail_pending", "بانتظار بريد"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_events",
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.IN_APP,
        db_index=True,
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link_url = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="nf_user_created_idx"),
        ]
        verbose_name = "إشعار"
        verbose_name_plural = "إشعارات"

    def __str__(self) -> str:
        return self.title


# ---------------------------------------------------------------------------
# طلب موافقة لإجراءات حساسة (الاعتماد اليدوي أولًا؛ لا يطبِّق تلقائيًا لتفادي الخطأ).
# ---------------------------------------------------------------------------
class SensitiveApprovalRequest(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "في الانتظار"
        APPROVED = "approved", "مقبول"
        REJECTED = "rejected", "مرفوض"

    action_key = models.CharField(max_length=64, db_index=True, help_text="مفتاح المجموعة مثل price_change أو debt_waiver")
    summary = models.CharField(max_length=255)
    detail = models.JSONField(default=dict, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    status = models.CharField(
        max_length=14,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"], name="saf_status_idx")]
        verbose_name = "موافقة إجراء"
        verbose_name_plural = "موافقة الإجراءات"

    def __str__(self) -> str:
        return f"{self.summary} [{self.status}]"


class AppErrorLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    path = models.CharField(max_length=255, blank=True)
    error_type = models.CharField(max_length=120, blank=True)
    message = models.TextField(blank=True)
    traceback_text = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["-created_at"], name="apperr_created_idx")]

    def __str__(self) -> str:
        return f"{self.created_at} {self.error_type}"
