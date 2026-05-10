"""قواعد عمولة ديناميكية؛ في غياب قاعدة مطابقة تُستخدم إعدادات المندوب الخاص بالطلب."""

from __future__ import annotations

from decimal import Decimal

from core.models import CommissionRule

from orders.models import Order


def resolved_commission_rate_and_fixed(order: Order) -> tuple[Decimal, Decimal]:
    """يُعاد (نسبة من الشحن، خصم/ثابت يُطبّق وفق المنطق الحالي خارج الشحن على مستوى المندوب اليومي)."""

    qr = CommissionRule.objects.filter(is_active=True).order_by("-priority", "-id")
    m_id = getattr(order.merchant, "pk", None)
    d_id = getattr(order.delegate, "pk", None)
    b_id = getattr(order.branch, "pk", None)

    best: CommissionRule | None = None
    best_score = -1

    for rule in qr:
        score = 0
        if rule.merchant_id is None:
            score += 0
        elif rule.merchant_id == m_id:
            score += 40
        else:
            continue
        if rule.delegate_id is None:
            score += 0
        elif rule.delegate_id == d_id:
            score += 30
        else:
            continue
        if rule.branch_id is None:
            score += 0
        elif rule.branch_id == b_id:
            score += 20
        else:
            continue
        if score > best_score:
            best_score = score
            best = rule

    if best is not None:
        return (
            Decimal(best.commission_rate or "0").quantize(Decimal("0.0001")),
            Decimal(best.fixed_addon or "0").quantize(Decimal("0.01")),
        )

    d = order.delegate
    if d:
        return (
            Decimal(d.commission_rate or "0").quantize(Decimal("0.0001")),
            Decimal("0"),
        )

    return (Decimal("0"), Decimal("0"))


def shipping_commission_amount(order: Order) -> Decimal:
    rate, fixed_addon = resolved_commission_rate_and_fixed(order)
    ship = order.shipping_price or Decimal("0")
    return (ship * rate + fixed_addon).quantize(Decimal("0.01"))
