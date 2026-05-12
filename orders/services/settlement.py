"""
عرض التسوية — محسوب فقط من بيانات التشغيل والحركات القائمة (لا يُخزَّن في الطلب كحالة مستقلة).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db import models
from django.db.models import Sum

from core.models import LedgerEntry
from merchants.models import MerchantPayment

from orders.models import Order, OrderStatus

from orders.services.accounting import _delegate_commission


class SettlementComputationState(models.TextChoices):
    CLEAR = "clear", "متوازن"
    MERCHANT_OWES = "merchant_owes", "التاجر عليه"
    COMPANY_OWES = "company_owes", "الشركة عليها"
    PENDING_RETURN = "pending_return", "مرتجع معلّق"
    UNSETTLED = "unsettled", "بحاجة لمراجعة"


@dataclass
class SettlementView:
    collected_amount: Decimal
    shipping_income_operational: Decimal
    courier_commission_estimate: Decimal
    merchant_payable_estimate: Decimal
    company_profit_estimate: Decimal
    returned_value: Decimal
    remaining_balance_hint: Decimal
    state_label: str
    state_code: str
    arabic_notes: str


def _sum_qs(qs, field):
    r = qs.aggregate(s=Sum(field))["s"]
    return Decimal(r or "0").quantize(Decimal("0.01"))


def _payments_for(order: Order, token: str):
    return MerchantPayment.objects.filter(notes__contains=f"order:{order.pk}:{token}")


def compute_order_settlement(order: Order) -> SettlementView:
    prod = Decimal(order.product_price or "0").quantize(Decimal("0.01"))
    ship = Decimal(order.shipping_price or "0").quantize(Decimal("0.01"))
    commission = _delegate_commission(order)
    status = order.status

    arabic_notes: list[str] = [
        "هذا المعطى مركَب آلياً لعرض تسوية تقديرية ولا يستبدل استلام السجلات المعتادة."
    ]

    ledger_collected = _sum_qs(
        LedgerEntry.objects.filter(order=order, entry_type=LedgerEntry.EntryType.COLLECTION),
        "amount",
    )
    ledger_shipping_margin = _sum_qs(
        LedgerEntry.objects.filter(order=order, entry_type=LedgerEntry.EntryType.SHIPPING_INCOME),
        "amount",
    )

    delivered_to_merchant = _sum_qs(_payments_for(order, "delivered").filter(direction="out"), "amount")
    accounted_from_merchant = _sum_qs(_payments_for(order, "accounted").filter(direction="in"), "amount")

    collected_amount = ledger_collected
    if status in (
        OrderStatus.DELIVERED,
        OrderStatus.PAID_TO_COMPANY,
        OrderStatus.PARTIALLY_DELIVERED,
        OrderStatus.PARTIALLY_DELIVERED_WITH_RETURN,
    ):
        collected_amount = max(collected_amount, prod)

    shipping_income = ship if status in (
        OrderStatus.DELIVERED,
        OrderStatus.PAID_TO_COMPANY,
        OrderStatus.PARTIALLY_DELIVERED,
        OrderStatus.PARTIALLY_DELIVERED_WITH_RETURN,
        OrderStatus.ACCOUNTED,
    ) else Decimal("0")
    courier_commission_estimate = (
        commission
        if status
        in (
            OrderStatus.DELIVERED,
            OrderStatus.PAID_TO_COMPANY,
            OrderStatus.PARTIALLY_DELIVERED,
            OrderStatus.PARTIALLY_DELIVERED_WITH_RETURN,
            OrderStatus.ACCOUNTED,
        )
        else Decimal("0")
    )

    merchant_payable = delivered_to_merchant if delivered_to_merchant > 0 else Decimal("0")
    if accounted_from_merchant > 0:
        arabic_notes.append("توجد مطالبات مسجَّلة لتاجر هذا الطلب وفقاً لحالة «حاسب أنت».")
        merchant_payable = accounted_from_merchant

    company_profit_estimate = ledger_shipping_margin
    if (
        shipping_income > 0
        and courier_commission_estimate >= 0
        and ledger_shipping_margin == 0
    ):
        rough = shipping_income - courier_commission_estimate
        company_profit_estimate = max(rough, Decimal("0")).quantize(Decimal("0.01"))

    fixed = Decimal("0")
    if getattr(order.delegate, "fixed_deduction", None):
        fixed = Decimal(order.delegate.fixed_deduction)

    returned_value = prod if status in (
        OrderStatus.RETURNED,
        OrderStatus.PARTIALLY_DELIVERED_WITH_RETURN,
    ) else Decimal("0")

    remaining_balance_hint = (collected_amount - merchant_payable).quantize(Decimal("0.01"))

    state_code = SettlementComputationState.UNSETTLED
    if status in (OrderStatus.RETURNED, OrderStatus.PARTIALLY_DELIVERED_WITH_RETURN):
        state_code = SettlementComputationState.PENDING_RETURN
    elif merchant_payable > 0 and collected_amount >= merchant_payable:
        state_code = SettlementComputationState.CLEAR
    elif merchant_payable > collected_amount and merchant_payable > 0:
        state_code = SettlementComputationState.MERCHANT_OWES
    elif merchant_payable == 0 and collected_amount > 0 and status == OrderStatus.DELIVERED:
        state_code = SettlementComputationState.CLEAR

    state_label = dict(SettlementComputationState.choices).get(state_code, str(state_code))

    return SettlementView(
        collected_amount=_decimal(collected_amount),
        shipping_income_operational=_decimal(shipping_income),
        courier_commission_estimate=_decimal(courier_commission_estimate + fixed),
        merchant_payable_estimate=_decimal(merchant_payable),
        company_profit_estimate=_decimal(company_profit_estimate),
        returned_value=_decimal(returned_value),
        remaining_balance_hint=_decimal(remaining_balance_hint),
        state_label=state_label,
        state_code=state_code,
        arabic_notes=" ".join(arabic_notes),
    )


def _decimal(v: Decimal) -> Decimal:
    return Decimal(v or "0").quantize(Decimal("0.01"))
