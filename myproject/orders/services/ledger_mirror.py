"""مرآة قراءات لـ LedgerEntry الموازية للقيود المعمول بها تاريخياً."""

from decimal import Decimal

from core.models import LedgerEntry


def _entity_customer(order) -> str:
    return f"customer:{order.pk}"


def _entity_courier(order) -> str:
    if order.delegate_id:
        return f"courier:{order.delegate_id}"
    return "courier:none"


def _entity_merchant(order) -> str:
    if order.merchant_id:
        return f"merchant:{order.merchant_id}"
    return "merchant:none"


def _entity_company_treasury() -> str:
    return "company:treasury_internal"


def mirror_delivery_ledger(
    order,
    *,
    company_profit: Decimal,
    product_collection: Decimal,
    branch=None,
    notes_suffix: str = "",
) -> None:
    suf = notes_suffix.strip()
    b = getattr(order, "branch_id", None)
    bids = getattr(branch, "pk", None) or b

    if company_profit > 0:
        LedgerEntry.objects.get_or_create(
            idempotency_key=f"ord-{order.pk}-delivered-profit",
            defaults={
                "from_entity": _entity_courier(order),
                "to_entity": _entity_company_treasury(),
                "amount": company_profit,
                "entry_type": LedgerEntry.EntryType.SHIPPING_INCOME,
                "order_id": order.pk,
                "branch_id": bids,
                "note": ("ربح تقديري من تسليم " + suf).strip(),
            },
        )

    if product_collection > 0:
        LedgerEntry.objects.get_or_create(
            idempotency_key=f"ord-{order.pk}-delivered-collection",
            defaults={
                "from_entity": _entity_customer(order),
                "to_entity": _entity_courier(order),
                "amount": product_collection,
                "entry_type": LedgerEntry.EntryType.COLLECTION,
                "order_id": order.pk,
                "branch_id": bids,
                "note": ("تحصيل سعر منتج بعد تسليم " + suf).strip(),
            },
        )
        LedgerEntry.objects.get_or_create(
            idempotency_key=f"ord-{order.pk}-delivered-merchant-due",
            defaults={
                "from_entity": _entity_courier(order),
                "to_entity": _entity_merchant(order),
                "amount": product_collection,
                "entry_type": LedgerEntry.EntryType.MERCHANT_PAYMENT,
                "order_id": order.pk,
                "branch_id": bids,
                "note": ("مستحق للتاجر بعد تسليم " + suf).strip(),
            },
        )


def mirror_accounted_ledger(
    order,
    *,
    company_fee: Decimal,
    courier_product_out: Decimal,
    merchant_claim: Decimal,
    branch=None,
    notes_suffix: str = "",
) -> None:
    suf = notes_suffix.strip()
    b = getattr(order, "branch_id", None)
    bids = getattr(branch, "pk", None) or b

    if company_fee > 0:
        LedgerEntry.objects.get_or_create(
            idempotency_key=f"ord-{order.pk}-accounted-fee",
            defaults={
                "from_entity": "virtual:settlement_fee",
                "to_entity": _entity_company_treasury(),
                "amount": company_fee,
                "entry_type": LedgerEntry.EntryType.ADJUSTMENT,
                "order_id": order.pk,
                "branch_id": bids,
                "note": ("تسوية حاسب أنت — رسم رمزي " + suf).strip(),
            },
        )

    if courier_product_out > 0:
        LedgerEntry.objects.get_or_create(
            idempotency_key=f"ord-{order.pk}-accounted-courier-out",
            defaults={
                "from_entity": _entity_courier(order),
                "to_entity": _entity_company_treasury(),
                "amount": courier_product_out,
                "entry_type": LedgerEntry.EntryType.TRANSFER,
                "order_id": order.pk,
                "branch_id": bids,
                "note": ("خصم مندوب حاسب أنت " + suf).strip(),
            },
        )

    if merchant_claim > 0:
        LedgerEntry.objects.get_or_create(
            idempotency_key=f"ord-{order.pk}-accounted-merchant-claim",
            defaults={
                "from_entity": _entity_merchant(order),
                "to_entity": _entity_company_treasury(),
                "amount": merchant_claim,
                "entry_type": LedgerEntry.EntryType.MERCHANT_PAYMENT,
                "order_id": order.pk,
                "branch_id": bids,
                "note": ("مطالبة تاجر على حاسب أنت " + suf).strip(),
            },
        )
