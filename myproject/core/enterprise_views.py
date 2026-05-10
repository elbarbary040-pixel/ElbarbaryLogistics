"""واجهات تشغيل موسّعة (ديون، مخزون إشعار، مخاطر مبدئية، موافقات) بدون المس بالجداول القديمة."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (
    Debt,
    DebtRepayment,
    InventoryMovement,
    MerchantStockItem,
    NotificationEvent,
    SensitiveApprovalRequest,
    TreasuryEntry,
)
from core.notifications import notify_admin_users
from core.permissions import is_admin_level
from merchants.models import Merchant, MerchantPayment

from delegates.models import Delegate


@login_required
def enterprise_hub(request):
    if not is_admin_level(request.user):
        messages.error(request, "هذه المنطقة للموظّفين الإداريّين.")
        return redirect("dashboard")

    ctx = {
        "debt_open": Debt.objects.exclude(status=Debt.Status.CLOSED).count(),
        "skus_count": MerchantStockItem.objects.count(),
        "risk_flags": treasury_duplicate_count() + ambiguous_payment_rows(),
        "pending_approvals": SensitiveApprovalRequest.objects.filter(status=SensitiveApprovalRequest.ApprovalStatus.PENDING).count(),
        "notifications_unread": NotificationEvent.objects.filter(user=request.user, read_at__isnull=True).count(),
    }
    return render(request, "core/enterprise_hub.html", ctx)


def treasury_duplicate_count() -> int:
    return (
        TreasuryEntry.objects.filter(order_id__isnull=False)
        .values("order_id", "reason")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
        .count()
    )


def ambiguous_payment_rows() -> int:
    return (
        MerchantPayment.objects.values("merchant_id", "notes")
        .annotate(c=Count("id"))
        .filter(c__gt=1, notes__contains="order:")
        .count()
    )


@login_required
def enterprise_debts(request):
    if not is_admin_level(request.user):
        return redirect("dashboard")
    qs = Debt.objects.select_related("merchant", "delegate", "order").order_by("-created_at")[:250]
    if request.method == "POST" and request.POST.get("create_debt") == "1":
        title = (request.POST.get("title") or "").strip()
        amt = Decimal(str(request.POST.get("amount_total") or "0").replace(",", ""))
        m_id = (request.POST.get("merchant_id") or "").strip()
        d_id = (request.POST.get("delegate_id") or "").strip()
        reason = (request.POST.get("reason") or "").strip()
        oid = (request.POST.get("order_id") or "").strip()
        if not title or amt <= 0:
            messages.error(request, "العنوان والمبلغ مطلوبان.")
            return redirect("core:enterprise_debts")
        debt_kwargs = {"title": title, "amount_total": amt.quantize(Decimal("0.01")), "reason": reason}
        if m_id.isdigit():
            debt_kwargs["merchant_id"] = int(m_id)
        if d_id.isdigit():
            debt_kwargs["delegate_id"] = int(d_id)
        if oid.isdigit():
            debt_kwargs["order_id"] = int(oid)
        try:
            d = Debt(**debt_kwargs)
            d.full_clean()
            d.save()
            notify_admin_users("تسجيل دين أو مستحقّة جديدة", title, "")
            messages.success(request, "تم إنشاء سجل مستحقّة.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("core:enterprise_debts")
    return render(
        request,
        "core/enterprise_debts.html",
        {
            "debts": qs,
            "merchants": Merchant.objects.order_by("name")[:500],
            "delegates": Delegate.objects.order_by("name")[:500],
        },
    )


@login_required
def enterprise_inventory(request):
    if not is_admin_level(request.user):
        return redirect("dashboard")
    items = MerchantStockItem.objects.select_related("merchant").order_by("-updated_at")[:300]
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_sku":
            mid = request.POST.get("merchant_id")
            label = (request.POST.get("label") or "").strip()
            sku = (request.POST.get("sku_code") or "").strip()
            qty = int(request.POST.get("quantity") or 0)
            if not mid.isdigit() or not label:
                messages.error(request, "تاجر ومسمّى الصنف مطلوبان.")
            else:
                obj = MerchantStockItem.objects.create(
                    merchant_id=int(mid),
                    label=label[:200],
                    sku_code=sku[:60],
                    quantity_on_hand=qty,
                )
                messages.success(request, f"تم إنشاء صنف رقم #{obj.pk}.")
            return redirect("core:enterprise_inventory")
        if action == "move":
            item_id = request.POST.get("item_id")
            delta = int(request.POST.get("delta") or 0)
            reason = request.POST.get("reason") or InventoryMovement.Reason.ADJUST
            if not item_id.isdigit():
                messages.error(request, "صنف غير صالح.")
            elif delta == 0:
                messages.error(request, "أدخل حركة غير صفرية.")
            else:
                it = get_object_or_404(MerchantStockItem, pk=int(item_id))
                InventoryMovement.objects.create(item=it, delta=delta, reason=reason[:32], note=(request.POST.get("note") or "")[:255])
                messages.success(request, "تم تسجيل حركة المخزون.")
            return redirect("core:enterprise_inventory")
    return render(
        request,
        "core/enterprise_inventory.html",
        {"items": items, "merchants": Merchant.objects.order_by("name")[:500], "movement_reasons": InventoryMovement.Reason.choices},
    )


@login_required
def notifications_center(request):
    if not is_admin_level(request.user):
        return redirect("dashboard")

    unread = NotificationEvent.objects.filter(user=request.user, read_at__isnull=True).order_by("-created_at")[:100]
    read = NotificationEvent.objects.filter(user=request.user, read_at__isnull=False).order_by("-created_at")[:50]
    if request.method == "POST" and request.POST.get("mark_read") == "1":
        ids = request.POST.getlist("nids")
        valid = []
        for x in ids:
            try:
                valid.append(int(x))
            except ValueError:
                continue
        if valid:
            NotificationEvent.objects.filter(user=request.user, pk__in=valid).update(read_at=timezone.now())
            messages.success(request, "حدُّثَت رسائل كمقروءة.")
        return redirect("core:notifications_center")
    return render(request, "core/notifications_center.html", {"unread": unread, "read": read})


@login_required
def risk_engine_stub(request):
    if not getattr(request.user, "is_superuser", False):
        messages.error(request, "المخاطر الموسّعة للمدير العام فقط في هذه المرحلة.")
        return redirect("core:enterprise_hub")

    dup_treas = (
        TreasuryEntry.objects.exclude(order__isnull=True)
        .values("order_id", "reason")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
        .order_by("-c")[:40]
    )
    dup_pay = (
        MerchantPayment.objects.values("merchant_id", "notes")
        .annotate(c=Count("id"))
        .filter(c__gt=1, notes__contains="order:")
        .order_by("-c")[:40]
    )

    return render(
        request,
        "core/risk_signals.html",
        {
            "dup_treas": dup_treas,
            "dup_pay": dup_pay,
        },
    )


@login_required
def approvals_queue(request):
    if not getattr(request.user, "is_superuser", False):
        messages.error(request, "صف الموافقة للمدير العام الآن.")
        return redirect("core:enterprise_hub")
    rows = SensitiveApprovalRequest.objects.order_by("-created_at")[:200]
    return render(request, "core/approvals_queue.html", {"rows": rows})


@login_required
def approval_decide(request, pk: int):
    if request.method != "POST" or not getattr(request.user, "is_superuser", False):
        return redirect("core:enterprise_approvals")
    row = get_object_or_404(SensitiveApprovalRequest, pk=pk)
    verdict = request.POST.get("verdict")
    if verdict == "approve":
        row.status = SensitiveApprovalRequest.ApprovalStatus.APPROVED
    elif verdict == "reject":
        row.status = SensitiveApprovalRequest.ApprovalStatus.REJECTED
    else:
        messages.error(request, "قرار غير معروف.")
        return redirect("core:enterprise_approvals")
    row.reviewed_by = request.user
    row.reviewed_at = timezone.now()
    row.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    notify_admin_users("تمّت المراجعة", f"{row.summary} — {row.get_status_display()}", "")
    messages.success(request, "تم ضبط حالة الموافقة (لا يطبّق النظام تغييرات آلية بعد).")
    return redirect("core:enterprise_approvals")


@login_required
def offline_help(request):
    return render(request, "core/offline_help.html")


@login_required
def enterprise_debt_repay(request, debt_id: int):
    debt = get_object_or_404(Debt, pk=debt_id)
    if request.method != "POST" or not is_admin_level(request.user):
        return redirect("core:enterprise_debts")
    amt = Decimal(str(request.POST.get("amount") or "0").replace(",", ""))
    if amt <= 0:
        messages.error(request, "مبلغ غير صالح.")
        return redirect("core:enterprise_debts")
    DebtRepayment.objects.create(
        debt=debt,
        amount=amt.quantize(Decimal("0.01")),
        notes=(request.POST.get("notes") or "")[:255],
    )
    notify_admin_users("تم تسديد جزء من مستحقّة", str(debt), "")
    messages.success(request, "سُجّل السداد.")
    return redirect("core:enterprise_debts")

