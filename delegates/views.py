from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from core.audit import log_action
from core.http_utils import query_first_str
from core.forms import UserEditForm
from core.models import AuditAction, UserRole
from core.permissions import can_manage_staff_records, is_admin_level, orders_queryset_for_user

from orders.models import Order, OrderStatus

_ORDER_STATUS_CODES = tuple(c for c, _ in OrderStatus.choices)

from .forms import DelegateDailyMetricForm, DelegateForm, DelegateSettlementItemForm, DelegateTransactionForm
from .models import Delegate, DelegateDailyClose, DelegateDailyMetric, DelegateSettlementItem, DelegateTransaction, DelegateTransactionType

User = get_user_model()


def _subtotal(values) -> Decimal:
    total = Decimal("0")
    for value in values:
        if value is None:
            continue
        total += Decimal(str(value))
    return total


@login_required
def delegate_list(request):
    if not is_admin_level(request.user):
        own = Delegate.objects.filter(linked_user=request.user).first()
        if own:
            return redirect("delegates:detail", delegate_id=own.pk)
    query = query_first_str(request.GET, "q")

    delegates = Delegate.objects.all()
    if query:
        delegates = delegates.filter(Q(name__icontains=query) | Q(phone__icontains=query))

    delegates = delegates.annotate(
        total_orders=Count("orders", distinct=True),
        delivered_orders=Count("orders", filter=Q(orders__status=OrderStatus.DELIVERED), distinct=True),
        in_transit_orders=Count("orders", filter=Q(orders__status=OrderStatus.IN_TRANSIT), distinct=True),
        accounted_orders=Count("orders", filter=Q(orders__status=OrderStatus.ACCOUNTED), distinct=True),
        delivered_shipping_total=Sum("orders__shipping_price", filter=Q(orders__status=OrderStatus.DELIVERED)),
    ).order_by("name")

    paginator = Paginator(delegates, 24)
    page_obj = paginator.get_page(query_first_str(request.GET, "page") or 1)

    querystring = request.GET.copy()
    querystring.pop("page", None)
    base_qs = querystring.urlencode()

    return render(
        request,
        "delegates/delegate_list.html",
        {"page_obj": page_obj, "base_qs": base_qs},
    )


@login_required
def delegate_add(request):
    if request.method == "POST":
        form = DelegateForm(request.POST)
        if form.is_valid():
            delegate = form.save()
            log_action(request, AuditAction.CREATE, delegate, "إضافة مندوب")
            messages.success(request, f"تم إضافة المندوب: {delegate.name}")
            return redirect("delegates:detail", delegate_id=delegate.id)
    else:
        form = DelegateForm()

    return render(request, "delegates/delegate_form.html", {"form": form})


@login_required
def delegate_edit(request, delegate_id: int):
    if not can_manage_staff_records(request.user):
        messages.error(request, "لا صلاحية لتعديل المندوب.")
        return redirect("dashboard")
    delegate = get_object_or_404(Delegate, pk=delegate_id)
    linked = delegate.linked_user
    user_form = None
    if linked:
        user_form = UserEditForm(instance=linked)

    if request.method == "POST":
        if request.POST.get("save_linked_user") == "1" and linked and user_form is not None:
            user_form = UserEditForm(request.POST, instance=linked)
            form = DelegateForm(instance=delegate)
            if user_form.is_valid():
                user_form.save()
                log_action(request, AuditAction.UPDATE, linked, "تحديث حساب المستخدم المرتبط بالمندوب")
                messages.success(request, "تم تحديث بيانات الدخول للمستخدم المرتبط.")
                return redirect("delegates:edit", delegate_id=delegate.pk)
        else:
            form = DelegateForm(request.POST, instance=delegate)
            if linked:
                user_form = UserEditForm(instance=linked)
            if form.is_valid():
                form.save()
                log_action(request, AuditAction.UPDATE, delegate, "تعديل بيانات المندوب")
                messages.success(request, "تم حفظ بيانات المندوب.")
                return redirect("delegates:detail", delegate_id=delegate.pk)
    else:
        form = DelegateForm(instance=delegate)
        if linked:
            user_form = UserEditForm(instance=linked)

    return render(
        request,
        "delegates/delegate_edit.html",
        {"form": form, "delegate": delegate, "user_form": user_form, "linked_user": linked},
    )


@login_required
def delegate_soft_delete(request, delegate_id: int):
    if not can_manage_staff_records(request.user):
        messages.error(request, "لا صلاحية للحذف.")
        return redirect("delegates:list")
    delegate = get_object_or_404(Delegate, pk=delegate_id)
    if request.method != "POST":
        return redirect("delegates:list")
    name = delegate.name
    delegate.soft_delete(request.user)
    log_action(request, AuditAction.DELETE, delegate, f"حذف منطقي للمندوب {name}")
    messages.success(request, "تم إخفاء المندوب من القوائم (حذف منطقي).")
    return redirect("delegates:list")


@login_required
def delegate_detail(request, delegate_id: int):
    delegate = get_object_or_404(Delegate, pk=delegate_id)
    if not is_admin_level(request.user) and delegate.linked_user_id != request.user.id:
        messages.error(request, "غير مسموح.")
        return redirect("dashboard")

    orders = orders_queryset_for_user(request.user).select_related("merchant", "delegate").filter(
        delegate=delegate
    )

    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    date_value = (request.GET.get("date") or "").strip()
    start_date_value = (request.GET.get("start_date") or "").strip()
    end_date_value = (request.GET.get("end_date") or "").strip()

    if query:
        orders = orders.filter(
            Q(waybill_number__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(customer_phone__icontains=query)
            | Q(customer_address__icontains=query)
            | Q(merchant__name__icontains=query)
            | Q(merchant__phone__icontains=query)
        )

    if status in _ORDER_STATUS_CODES:
        orders = orders.filter(status=status)

    parsed_date = parse_date(date_value) if date_value else None
    parsed_start_date = parse_date(start_date_value) if start_date_value else None
    parsed_end_date = parse_date(end_date_value) if end_date_value else None

    if parsed_date:
        orders = orders.filter(order_date=parsed_date)
    else:
        if parsed_start_date:
            orders = orders.filter(order_date__gte=parsed_start_date)
        if parsed_end_date:
            orders = orders.filter(order_date__lte=parsed_end_date)

    summary = orders.aggregate(
        orders_count=Count("id"),
        product_total=Sum("product_price"),
        shipping_total=Sum("shipping_price"),
        delivered_count=Count("id", filter=Q(status=OrderStatus.DELIVERED)),
        in_transit_count=Count("id", filter=Q(status=OrderStatus.IN_TRANSIT)),
        accounted_count=Count("id", filter=Q(status=OrderStatus.ACCOUNTED)),
    )

    settlement_date = parsed_date or timezone.localdate()
    settlement_orders = orders_queryset_for_user(request.user).filter(
        delegate=delegate,
        order_date=settlement_date,
    )

    daily_closed = DelegateDailyClose.objects.filter(
        delegate=delegate, close_date=settlement_date
    ).exists()

    if request.method == "POST" and request.POST.get("promote_login") == "1":
        if not is_admin_level(request.user):
            messages.error(request, "غير مسموح.")
            return redirect(request.get_full_path())
        if delegate.linked_user:
            messages.info(request, f"هذا المندوب مرتبط بالفعل بالمستخدم: {delegate.linked_user.username}")
            return redirect(request.get_full_path())
        slug = slugify(delegate.name or "", allow_unicode=True).replace("-", "")[:12]
        username_base = slug or f"d{delegate.pk}"
        username = f"{username_base}_{delegate.pk}"
        while User.objects.filter(username=username).exists():
            username = f"{username_base}_{delegate.pk}_{get_random_string(3).lower()}"
        password = get_random_string(10)
        user = User.objects.create_user(username=username, password=password, is_active=True)
        prof = user.profile
        prof.role = UserRole.DELEGATE
        prof.save(update_fields=["role"])
        delegate.linked_user = user
        delegate.save(update_fields=["linked_user"])
        messages.success(
            request,
            f"تمت الترقية. سجّل الدخول باسم المستخدم (نسخه كما هو): {username} — كلمة المرور: {password}",
        )
        return redirect(request.get_full_path())

    if request.method == "POST" and request.POST.get("daily_close") == "1":
        if not is_admin_level(request.user):
            messages.error(request, "غير مسموح.")
        else:
            DelegateDailyClose.objects.get_or_create(
                delegate=delegate,
                close_date=settlement_date,
                defaults={"closed_by": request.user},
            )
            messages.success(request, "تم تسجيل توريد اليوم.")
        return redirect(request.get_full_path())

    if request.method == "POST" and request.POST.get("bulk_action"):
        action = (request.POST.get("bulk_action") or "").strip()
        selected_order_ids = [x for x in request.POST.getlist("order_ids") if x.isdigit()]
        if not selected_order_ids:
            messages.error(request, "اختار أوردر واحد على الأقل.")
            return redirect(request.get_full_path())
        ids_csv = ",".join(selected_order_ids)
        if action == "export_excel":
            return redirect(f"{reverse('orders:export')}?ids={ids_csv}")
        if action == "print":
            return redirect(f"{reverse('orders:print')}?ids={ids_csv}")
        if action == "qr":
            return redirect(f"{reverse('orders:qr')}?ids={ids_csv}")
        if action == "whatsapp":
            from urllib.parse import quote

            from orders.whatsapp_ar import build_bulk_whatsapp_text_ar

            body = build_bulk_whatsapp_text_ar(
                orders.filter(pk__in=selected_order_ids)
                .select_related("merchant", "delegate")
                .order_by("waybill_number"),
            )
            return redirect("https://wa.me/?text=" + quote(body))
        if action == "bulk_status":
            status = (request.POST.get("new_status") or "").strip()
            if status not in _ORDER_STATUS_CODES:
                messages.error(request, "حالة غير صالحة.")
                return redirect(request.get_full_path())
            updated = 0
            for o in orders.filter(pk__in=selected_order_ids):
                if o.status == status:
                    continue
                o.status = status
                o.updated_by = request.user
                setattr(o, "_save_user", request.user)
                o.save(update_fields=["status", "updated_at", "updated_by"])
                updated += 1
            messages.success(request, f"تم تحديث حالة {updated} شحنة.")
            return redirect(request.get_full_path())
        messages.error(request, "إجراء غير معروف.")
        return redirect(request.get_full_path())

    if request.method == "POST" and request.POST.get("tx_form") == "1":
        tx_form = DelegateTransactionForm(request.POST)
        if tx_form.is_valid():
            tx = tx_form.save(commit=False)
            tx.delegate = delegate
            tx.save()
            log_action(request, AuditAction.CREATE, tx, "تسجيل حركة مندوب")
            messages.success(request, "تم تسجيل الحركة بنجاح.")
            try:
                from core.notifications import notify_admin_users

                notify_admin_users("حركة مندوب مسجَّلة", f"{delegate.name} — {tx.amount}", "")
            except Exception:
                pass
            return redirect(request.get_full_path())
    else:
        tx_form = DelegateTransactionForm(initial={"transaction_date": settlement_date})

    if request.method == "POST" and request.POST.get("settlement_item_form") == "1":
        settlement_item_form = DelegateSettlementItemForm(request.POST)
        if settlement_item_form.is_valid():
            si = settlement_item_form.save(commit=False)
            si.delegate = delegate
            si.save()
            messages.success(request, "تم إضافة بند التصفية.")
            return redirect(request.get_full_path())
    else:
        settlement_item_form = DelegateSettlementItemForm(initial={"item_date": settlement_date})

    metric_obj, _ = DelegateDailyMetric.objects.get_or_create(delegate=delegate, metric_date=settlement_date)
    if request.method == "POST" and request.POST.get("metric_form") == "1":
        metric_form = DelegateDailyMetricForm(request.POST, instance=metric_obj)
        if metric_form.is_valid():
            metric_form.save()
            messages.success(request, "تم حفظ أرقام التصفية اليدوية.")
            return redirect(request.get_full_path())
    else:
        metric_form = DelegateDailyMetricForm(instance=metric_obj)

    transactions = DelegateTransaction.objects.filter(delegate=delegate, transaction_date=settlement_date).order_by("-id")
    tx_summary = transactions.aggregate(
        in_total=Sum("amount", filter=Q(direction="in")),
        out_total=Sum("amount", filter=Q(direction="out")),
    )
    settlement_items = DelegateSettlementItem.objects.filter(delegate=delegate, item_date=settlement_date).order_by("-id")

    # المعادلات اليومية حسب القواعد التشغيلية:
    # - عهدة: تبدأ من 0 وتضاف يدويًا من حركات "عهدة" (داخل).
    # - توتال: العهدة + (شحن + منتج) لكل الحالات، لكن في "حاسب أنت" نخصم المنتج فقط.
    # - الشغل: مجموع الشحن لكل الحالات ما عدا "في الطريق".
    # - القبض: عمولة المندوب (نسبة من الشغل، أو قيمة ثابتة عند غياب النسبة).
    # - الصافي: التوتال - القبض.
    advance_total_calc = (
        DelegateTransaction.objects.filter(
            delegate=delegate,
            transaction_date=settlement_date,
            tx_type=DelegateTransactionType.ADVANCE,
            direction="in",
        ).aggregate(s=Sum("amount"))["s"]
        or Decimal("0")
    )

    shipping_for_work = []
    total_value_calc = Decimal(str(advance_total_calc))
    delivered_product_total = Decimal("0")
    for o in settlement_orders:
        product = Decimal(str(o.product_price or Decimal("0")))
        shipping = Decimal(str(o.shipping_price or Decimal("0")))
        delivered_product_total += product
        if o.status == OrderStatus.ACCOUNTED:
            # "حاسب أنت": نخصم المنتج فقط مع إبقاء الشحن ضمن التوتال.
            total_value_calc += shipping - product
        else:
            total_value_calc += product + shipping
        if o.status != OrderStatus.IN_TRANSIT:
            shipping_for_work.append(shipping)

    extra_items_total = Decimal("0")
    for si in settlement_items:
        extra_items_total += (Decimal(si.quantity) * Decimal(si.unit_price)).quantize(Decimal("0.01"))
    total_value_calc = (total_value_calc + extra_items_total).quantize(Decimal("0.01"))

    work_total_calc = _subtotal(shipping_for_work).quantize(Decimal("0.01"))
    commission_rate = Decimal(str(delegate.commission_rate or Decimal("0")))
    fixed = Decimal(str(delegate.fixed_deduction or Decimal("0"))).quantize(Decimal("0.01"))
    if commission_rate > 0:
        cash_collected_calc = (work_total_calc * commission_rate).quantize(Decimal("0.01"))
    else:
        cash_collected_calc = fixed

    delegate_commission = cash_collected_calc
    successful_shipping_total = work_total_calc
    company_profit = (work_total_calc - delegate_commission).quantize(Decimal("0.01"))
    net_total_calc = (total_value_calc - cash_collected_calc).quantize(Decimal("0.01"))

    work_total = metric_obj.work_value if metric_obj.work_value is not None else work_total_calc
    cash_collected = metric_obj.cash_value if metric_obj.cash_value is not None else cash_collected_calc
    advance_total = metric_obj.advance_value if metric_obj.advance_value is not None else advance_total_calc
    items_total_value = metric_obj.total_value if metric_obj.total_value is not None else total_value_calc
    net_total = metric_obj.net_value if metric_obj.net_value is not None else net_total_calc

    paginator = Paginator(orders.order_by("-order_date", "-id"), 50)
    page_obj = paginator.get_page(query_first_str(request.GET, "page") or 1)

    querystring = request.GET.copy()
    querystring.pop("page", None)
    base_qs = querystring.urlencode()

    return render(
        request,
        "delegates/delegate_detail.html",
        {
            "delegate": delegate,
            "page_obj": page_obj,
            "base_qs": base_qs,
            "bulk_form_id": "orders-bulk-form",
            "summary": summary,
            "settlement_date": settlement_date,
            "successful_shipping_total": successful_shipping_total,
            "delegate_commission": delegate_commission,
            "fixed": fixed,
            "company_profit": company_profit,
            "transactions": transactions,
            "tx_summary": tx_summary,
            "tx_form": tx_form,
            "daily_closed": daily_closed,
            "is_self_delegate": delegate.linked_user_id == request.user.id,
            "settlement_item_form": settlement_item_form,
            "settlement_items": settlement_items,
            "items_total": items_total_value,
            "work_total": work_total,
            "cash_collected": cash_collected,
            "advance_total": advance_total,
            "net_total": net_total,
            "metric_form": metric_form,
        },
    )
