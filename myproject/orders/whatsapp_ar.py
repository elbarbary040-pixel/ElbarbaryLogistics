"""رسائل واتساب بالعربية فقط لتفاصيل الطلب وتقدير الحساب."""


def build_order_whatsapp_block_ar(order, settlement=None):
    ln = []

    ln.append(f"رقم الطلب الداخلي: {order.waybill_number}")
    if order.external_waybill:
        ln.append(f"رمز بوليصة الوكيل: {order.external_waybill}")

    ln.append(f"تاريخ الشحنة: {order.order_date}")
    ln.append(f"الحالة: {order.get_status_display()}")

    ln.append("")
    ln.append("— بيانات العميل —")
    ln.append(f"الاسم: {order.customer_name}")
    if order.customer_phone:
        ln.append(f"الهاتف: {order.customer_phone}")
    if order.customer_address:
        ln.append(f"العنوان: {order.customer_address}")

    ln.append("")
    ln.append("— التشغيل —")
    if order.merchant:
        ln.append(f"التاجر: {order.merchant.name}")
        if getattr(order.merchant, "phone", None):
            ln.append(f"هاتف التاجر: {order.merchant.phone}")
    else:
        ln.append("التاجر: غير محدد")

    if order.delegate:
        ln.append(f"المندوب: {order.delegate.name}")
        if getattr(order.delegate, "phone", None):
            ln.append(f"هاتف المندوب: {order.delegate.phone}")
    else:
        ln.append("المندوب: غير محدد")

    ln.append("")
    ln.append("— المنتج والشحن —")
    ln.append(f"سعر المنتج: {order.product_price} ج.م")
    ln.append(f"سعر الشحن: {order.shipping_price} ج.م")
    ln.append("")
    ln.append(
        "— تقدير مالي تشغيلي للمراجعة (لا يعتبر مخالصة قبل التأكيد مع الإدارة) —"
        if settlement
        else "— لم تُحمَّل بيانات تسوية مفصَّلة؛ راجع لوحة الطلب لمزيد من التفاصيل. —"
    )
    if settlement:
        ln.append(f"التقدير: التحقق من المتبقي: {settlement.remaining_balance_hint} ج.م")
        ln.append(f"التقدير: مستحق تجاري للتاجر: {settlement.merchant_payable_estimate} ج.م")
        ln.append(f"التقدير: عمولة مندوب وفق الأسعار المعروضة: {settlement.courier_commission_estimate} ج.م")
        ln.append(f"التقدير: شحن تشغيلي: {settlement.shipping_income_operational} ج.م")
        ln.append(f"التقدير: ربح شركة تقديري: {settlement.company_profit_estimate} ج.م")
        ln.append(f"التقدير: قيمة مرتجعات حسب السجل الحالي: {settlement.returned_value} ج.م")
        ln.append("")
        ln.append(f"حالة تصفية مبدئية: {settlement.state_label}")

    ln.append("")
    ln.append(f"رمز بحث الطلب الداخلي: {order.waybill_number}")

    if getattr(order, "notes", None) and order.notes.strip():
        ln.append("")
        ln.append("ملاحظات:")
        ln.append(order.notes.strip())

    return "\n".join(ln)


def build_bulk_whatsapp_text_ar(orders_iterable):
    blocks = []
    for o in orders_iterable:
        try:
            from orders.services.settlement import compute_order_settlement

            st = compute_order_settlement(o)
        except Exception:
            st = None
        blocks.append(build_order_whatsapp_block_ar(o, st))
    sep = "\n\n" + "═" * 18 + "\n\n"
    return sep.join(blocks)

