"""
تأثيرات مالية مبسطة عند تغيير حالة الأوردر.
المنطق الكامل للشركة يختلف من نظام لآخر؛ هنا نسجّل حركات واضحة يمكن تعديلها لاحقًا.

تم التسليم:
- ربح تقديري للخزنة الداخلية = شحن - (شحن × نسبة عمولة المندوب) بدون طرح الثابت لكل أوردر
  (الثابت يُحسب يوميًا في شاشة المندوب).
- عهدة مندوب: حركة ADVANCE وارد بقيمة سعر المنتج (تمثيل تحصيل من العميل).

مدفوع للشركة شامل الشحن:
- العميل دفع للشركة مباشرة (إنستا باي / تحويل / QR).
- الشركة استلمت المنتج + الشحن.
- التاجر له سعر المنتج فقط.
- لا عهدة على المندوب.

حاسب أنت:
- حركة خزنة داخلية بسبب order_accounted بمبلغ رمزي من الشحن (يمكن ضبطه لاحقًا).

في الطريق: لا حركات.

بالإضافة: تكرار الموازنة في LedgerEntry بدون استبدال الحقول المحاسبية القائمة.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from delegates.models import (
    DelegateTransaction,
    DelegateTransactionType,
    TransactionDirection,
)

from merchants.models import MerchantPayment, PaymentDirection

from core.models import (
    TreasuryAccount,
    TreasuryDirection,
    TreasuryEntry,
    TreasuryKind,
    TreasuryReason,
)

from ..models import Order, OrderStatus

User = get_user_model()


def _delegate_commission(order: Order) -> Decimal:
    from orders.services import commission_resolver

    return commission_resolver.shipping_commission_amount(order)


def apply_status_accounting(order: Order, old_status: str | None, new_status: str, user) -> None:
    if old_status == new_status:
        return

    user_id = (
        getattr(user, "pk", None)
        if user and getattr(user, "is_authenticated", False)
        else None
    )

    # استيراد مؤجل لتفادي أي حلقة تعريف بين الخدمات
    from orders.services.ledger_mirror import (
        mirror_accounted_ledger,
        mirror_delivery_ledger,
    )

    with transaction.atomic():
        _apply_inner(
            order,
            old_status,
            new_status,
            user_id,
            mirror_delivery_ledger,
            mirror_accounted_ledger,
        )


def _apply_inner(
    order,
    old_status,
    new_status,
    user_id,
    mirror_delivery_ledger,
    mirror_accounted_ledger,
):

    # =========================================================
    # تم التسليم
    # =========================================================
    if (
        new_status == OrderStatus.DELIVERED
        and old_status != OrderStatus.DELIVERED
    ):

        commission = _delegate_commission(order)

        profit = (
            order.shipping_price - commission
        ).quantize(Decimal("0.01"))

        if profit < 0:
            profit = Decimal("0")

        if not TreasuryEntry.objects.filter(
            order=order,
            reason=TreasuryReason.ORDER_DELIVERED_PROFIT,
        ).exists():

            acc = TreasuryAccount.objects.filter(
                kind=TreasuryKind.INTERNAL
            ).first()

            if acc and profit > 0:
                TreasuryEntry.objects.create(
                    account=acc,
                    entry_date=order.order_date,
                    amount=profit,
                    direction=TreasuryDirection.IN,
                    reason=TreasuryReason.ORDER_DELIVERED_PROFIT,
                    order=order,
                    notes="ربح تقديري من تسليم",
                    created_by_id=user_id,
                )

        # عهدة المندوب
        if order.delegate and order.product_price > 0:

            if not DelegateTransaction.objects.filter(
                delegate=order.delegate,
                notes__contains=f"order:{order.pk}:delivered",
            ).exists():

                DelegateTransaction.objects.create(
                    delegate=order.delegate,
                    transaction_date=order.order_date,
                    tx_type=DelegateTransactionType.ADVANCE,
                    direction=TransactionDirection.IN,
                    amount=order.product_price,
                    notes=f"عهدة تحصيل أوردر order:{order.pk}:delivered",
                )

        # مستحق التاجر
        if order.merchant and order.product_price > 0:

            if not MerchantPayment.objects.filter(
                merchant=order.merchant,
                notes__contains=f"order:{order.pk}:delivered",
            ).exists():

                MerchantPayment.objects.create(
                    merchant=order.merchant,
                    payment_date=order.order_date,
                    direction=PaymentDirection.OUT,
                    amount=order.product_price,
                    notes=f"مستحق تاجر بعد تسليم order:{order.pk}:delivered",
                )

        mirror_delivery_ledger(
            order,
            company_profit=profit,
            product_collection=(
                Decimal(order.product_price).quantize(Decimal("0.01"))
                if order.product_price > 0
                else Decimal("0")
            ),
            branch=getattr(order, "branch", None),
        )

    # =========================================================
    # مدفوع للشركة شامل الشحن
    # =========================================================
    if (
        new_status == OrderStatus.PAID_TO_COMPANY
        and old_status != OrderStatus.PAID_TO_COMPANY
    ):

        total_collected = (
            Decimal(order.product_price)
            + Decimal(order.shipping_price)
        ).quantize(Decimal("0.01"))

        # التاجر له سعر المنتج فقط
        if order.merchant and order.product_price > 0:

            if not MerchantPayment.objects.filter(
                merchant=order.merchant,
                notes__contains=f"order:{order.pk}:paid_to_company",
            ).exists():

                MerchantPayment.objects.create(
                    merchant=order.merchant,
                    payment_date=order.order_date,
                    direction=PaymentDirection.OUT,
                    amount=order.product_price,
                    notes=f"مستحق تاجر - دفع إلكتروني order:{order.pk}:paid_to_company",
                )

        # لا توجد عهدة على المندوب

        mirror_delivery_ledger(
            order,
            company_profit=Decimal(order.shipping_price).quantize(
                Decimal("0.01")
            ),
            product_collection=total_collected,
            branch=getattr(order, "branch", None),
        )

    # =========================================================
    # حاسب أنت
    # =========================================================
    if (
        new_status == OrderStatus.ACCOUNTED
        and old_status != OrderStatus.ACCOUNTED
    ):

        fee = (
            order.shipping_price * Decimal("0.05")
        ).quantize(Decimal("0.01"))

        accounted_total = (
            order.product_price + order.shipping_price
        ).quantize(Decimal("0.01"))

        if not TreasuryEntry.objects.filter(
            order=order,
            reason=TreasuryReason.ORDER_ACCOUNTED,
        ).exists():

            acc = TreasuryAccount.objects.filter(
                kind=TreasuryKind.INTERNAL
            ).first()

            if acc and fee > 0:

                TreasuryEntry.objects.create(
                    account=acc,
                    entry_date=order.order_date,
                    amount=fee,
                    direction=TreasuryDirection.IN,
                    reason=TreasuryReason.ORDER_ACCOUNTED,
                    order=order,
                    notes="تسوية حاسب أنت (نسبة رمزية من الشحن)",
                    created_by_id=user_id,
                )

        # خصم من عهدة المندوب
        if order.delegate and order.product_price > 0:

            if not DelegateTransaction.objects.filter(
                delegate=order.delegate,
                notes__contains=f"order:{order.pk}:accounted",
            ).exists():

                DelegateTransaction.objects.create(
                    delegate=order.delegate,
                    transaction_date=order.order_date,
                    tx_type=DelegateTransactionType.TRANSFER,
                    direction=TransactionDirection.OUT,
                    amount=order.product_price,
                    notes=f"خصم مندوب حاسب أنت order:{order.pk}:accounted",
                )

        # التاجر عليه المنتج + الشحن
        if order.merchant and accounted_total > 0:

            if not MerchantPayment.objects.filter(
                merchant=order.merchant,
                notes__contains=f"order:{order.pk}:accounted",
            ).exists():

                MerchantPayment.objects.create(
                    merchant=order.merchant,
                    payment_date=order.order_date,
                    direction=PaymentDirection.IN,
                    amount=accounted_total,
                    notes=f"على التاجر (حاسب أنت) order:{order.pk}:accounted",
                )

        mirror_accounted_ledger(
            order,
            company_fee=fee if fee > 0 else Decimal("0"),
            courier_product_out=(
                Decimal(order.product_price).quantize(Decimal("0.01"))
                if order.delegate and order.product_price > 0
                else Decimal("0")
            ),
            merchant_claim=(
                accounted_total
                if order.merchant and accounted_total > 0
                else Decimal("0")
            ),
            branch=getattr(order, "branch", None),
        )