from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from decimal import Decimal
from core.audit import log_action
from core.http_utils import query_first_str
from core.models import AuditAction, OrderRequest, UserRole
from core.forms import UserEditForm
from core.permissions import can_manage_staff_records, is_admin_level, orders_queryset_for_user
from orders.models import OrderStatus

from .forms import MerchantForm, MerchantPaymentForm
from .models import Merchant, MerchantPayment, PaymentDirection

User = get_user_model()

_ORDER_STATUS_CODES = tuple(c for c, _ in OrderStatus.choices)


@login_required
def merchant_list(request):
    if not is_admin_level(request.user):
        own = Merchant.objects.filter(linked_user=request.user).first()
        if own:
            return redirect("merchants:detail", merchant_id=own.pk)

    query = query_first_str(request.GET, "q")

    merchants = Merchant.objects.all()
    if query:
        merchants = merchants.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(address__icontains=query)
            | Q(brand_name__icontains=query)
        )

    merchants = merchants.annotate(
        total_orders=Count("orders", distinct=True),
        delivered_orders=Count("orders", filter=Q(orders__status=OrderStatus.DELIVERED), distinct=True),
        in_transit_orders=Count("orders", filter=Q(orders__status=OrderStatus.IN_TRANSIT), distinct=True),
        accounted_orders=Count("orders", filter=Q(orders__status=OrderStatus.ACCOUNTED), distinct=True),
        delivered_product_total=Sum("orders__product_price", filter=Q(orders__status=OrderStatus.DELIVERED)),
        delivered_shipping_total=Sum("orders__shipping_price", filter=Q(orders__status=OrderStatus.DELIVERED)),
    ).order_by("name")

    paginator = Paginator(merchants, 24)
    page_obj = paginator.get_page(query_first_str(request.GET, "page") or 1)

    querystring = request.GET.copy()
    querystring.pop("page", None)
    base_qs = querystring.urlencode()

    return render(
        request,
        "merchants/merchant_list.html",
        {"page_obj": page_obj, "base_qs": base_qs},
    )


@login_required
def merchant_add(request):
    if request.method == "POST":
        form = MerchantForm(request.POST)
        if form.is_valid():
            merchant = form.save()
            log_action(request, AuditAction.CREATE, merchant, "إضافة تاجر")
            messages.success(request, f"تم إضافة التاجر: {merchant.name}")
            return redirect("merchants:detail", merchant_id=merchant.id)
    else:
        form = MerchantForm()

    return render(request, "merchants/merchant_form.html", {"form": form})


@login_required
def merchant_edit(request, merchant_id: int):
    if not can_manage_staff_records(request.user):
        messages.error(request, "لا صلاحية لتعديل التاجر.")
        return redirect("dashboard")
    merchant = get_object_or_404(Merchant, pk=merchant_id)
    linked = merchant.linked_user
    user_form = None
    if linked:
        user_form = UserEditForm(instance=linked)

    if request.method == "POST":
        if request.POST.get("save_linked_user") == "1" and linked and user_form is not None:
            user_form = UserEditForm(request.POST, instance=linked)
            form = MerchantForm(instance=merchant)
            if user_form.is_valid():
                user_form.save()
                log_action(request, AuditAction.UPDATE, linked, "تحديث حساب المستخدم المرتبط بالتاجر")
                messages.success(request, "تم تحديث بيانات الدخول للمستخدم المرتبط.")
                return redirect("merchants:edit", merchant_id=merchant.pk)
        else:
            form = MerchantForm(request.POST, instance=merchant)
            if linked:
                user_form = UserEditForm(instance=linked)
            if form.is_valid():
                form.save()
                log_action(request, AuditAction.UPDATE, merchant, "تعديل بيانات التاجر")
                messages.success(request, "تم حفظ بيانات التاجر.")
                return redirect("merchants:detail", merchant_id=merchant.pk)
    else:
        form = MerchantForm(instance=merchant)
        if linked:
            user_form = UserEditForm(instance=linked)

    return render(
        request,
        "merchants/merchant_edit.html",
        {"form": form, "merchant": merchant, "user_form": user_form, "linked_user": linked},
    )


@login_required
def merchant_soft_delete(request, merchant_id: int):
    if not can_manage_staff_records(request.user):
        messages.error(request, "لا صلاحية للحذف.")
        return redirect("merchants:list")
    merchant = get_object_or_404(Merchant, pk=merchant_id)
    if request.method != "POST":
        return redirect("merchants:list")
    name = merchant.name
    merchant.soft_delete(request.user)
    log_action(request, AuditAction.DELETE, merchant, f"حذف منطقي للتاجر {name}")
    messages.success(request, "تم إخفاء التاجر من القوائم (حذف منطقي).")
    return redirect("merchants:list")


@login_required
def external_merchant_add(request):
    if not is_admin_level(request.user):
        messages.error(request, "غير مسموح.")
        return redirect("dashboard")
    if request.method == "POST":
        form = MerchantForm(request.POST)
        if form.is_valid():
            merchant = form.save(commit=False)
            merchant.is_external = True
            merchant.save()
            messages.success(request, f"تم إضافة التاجر الخارجي: {merchant.name}")
            return redirect("merchants:external_detail", merchant_id=merchant.id)
    else:
        form = MerchantForm()
    return render(request, "merchants/merchant_form.html", {"form": form})


@login_required
def merchant_detail(request, merchant_id: int):
    merchant = get_object_or_404(Merchant, pk=merchant_id)
    if not is_admin_level(request.user) and merchant.linked_user_id != request.user.id:
        messages.error(request, "غير مسموح.")
        return redirect("dashboard")

    orders = orders_queryset_for_user(request.user).select_related("merchant", "delegate").filter(
        merchant=merchant
    )
    if merchant.is_external:
        orders = orders.filter(external_waybill__isnull=False)

    query = query_first_str(request.GET, "q")
    status = query_first_str(request.GET, "status")
    date_value = query_first_str(request.GET, "date")
    start_date_value = query_first_str(request.GET, "start_date")
    end_date_value = query_first_str(request.GET, "end_date")

    if query:
        orders = orders.filter(
            Q(waybill_number__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(customer_phone__icontains=query)
            | Q(customer_address__icontains=query)
            | Q(delegate__name__icontains=query)
            | Q(delegate__phone__icontains=query)
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

    if request.method == "POST" and request.POST.get("promote_login") == "1":
        if not is_admin_level(request.user):
            messages.error(request, "غير مسموح.")
            return redirect(request.get_full_path())
        if merchant.linked_user:
            messages.info(request, f"هذا التاجر مرتبط بالفعل بالمستخدم: {merchant.linked_user.username}")
            return redirect(request.get_full_path())
        slug = slugify(merchant.name or "", allow_unicode=True).replace("-", "")[:12]
        username_base = slug or f"m{merchant.pk}"
        username = f"{username_base}_{merchant.pk}"
        while User.objects.filter(username=username).exists():
            username = f"{username_base}_{merchant.pk}_{get_random_string(3).lower()}"
        password = get_random_string(10)
        user = User.objects.create_user(username=username, password=password, is_active=True)
        prof = user.profile
        prof.role = UserRole.MERCHANT
        prof.save(update_fields=["role"])
        merchant.linked_user = user
        merchant.save(update_fields=["linked_user"])
        messages.success(
            request,
            f"تمت الترقية. سجّل الدخول باسم المستخدم (نسخه كما هو): {username} — كلمة المرور: {password}",
        )
        return redirect(request.get_full_path())

    if request.method == "POST" and request.POST.get("new_order_request") == "1":
        if merchant.linked_user_id != request.user.id:
            messages.error(request, "غير مسموح.")
            return redirect(request.get_full_path())
        customer_name = (request.POST.get("customer_name") or "").strip()
        if not customer_name:
            messages.error(request, "اسم العميل مطلوب.")
            return redirect(request.get_full_path())
        OrderRequest.objects.create(
            requester=request.user,
            merchant=merchant,
            customer_name=customer_name,
            customer_phone=(request.POST.get("customer_phone") or "").strip(),
            customer_address=(request.POST.get("customer_address") or "").strip(),
            product_price=request.POST.get("product_price") or 0,
            shipping_price=request.POST.get("shipping_price") or 0,
            notes=(request.POST.get("notes") or "").strip(),
        )
        messages.success(request, "تم إرسال طلب الشحنة للإدارة لاعتمادها.")
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

    if request.method == "POST" and request.POST.get("payment_form") == "1":
        payment_form = MerchantPaymentForm(request.POST)
        if payment_form.is_valid():
            payment = payment_form.save(commit=False)
            payment.merchant = merchant
            payment.save()
            log_action(request, AuditAction.CREATE, payment, "تسجيل حركة تاجر")
            messages.success(request, "تم تسجيل الحركة بنجاح.")
            try:
                from core.notifications import notify_admin_users

                notify_admin_users(
                    "حركة تاجر مسجَّلة",
                    f"{merchant.name} — اتجاه: {payment.get_direction_display()} — {payment.amount}",
                    "",
                )
            except Exception:
                pass
            return redirect(request.get_full_path())
    else:
        payment_form = MerchantPaymentForm()

    payments = MerchantPayment.objects.filter(merchant=merchant).order_by("-payment_date", "-id")[:50]

    paginator = Paginator(orders.order_by("-order_date", "-id"), 50)
    page_obj = paginator.get_page(query_first_str(request.GET, "page") or 1)

    querystring = request.GET.copy()
    querystring.pop("page", None)
    base_qs = querystring.urlencode()

    payments_summary = MerchantPayment.objects.filter(merchant=merchant).aggregate(
        in_total=Sum("amount", filter=Q(direction=PaymentDirection.IN)),
        out_total=Sum("amount", filter=Q(direction=PaymentDirection.OUT)),
    )
    payments_in_total = payments_summary["in_total"] or Decimal("0")
    payments_out_total = payments_summary["out_total"] or Decimal("0")
    net_under_account = (payments_in_total - payments_out_total).quantize(Decimal("0.01"))
    merchant_financials = {
        "delivered_product_due": orders.filter(status=OrderStatus.DELIVERED).aggregate(s=Sum("product_price"))["s"] or Decimal("0"),
        "accounted_total_on_merchant": (
            (orders.filter(status=OrderStatus.ACCOUNTED).aggregate(s=Sum("product_price"))["s"] or Decimal("0"))
            + (orders.filter(status=OrderStatus.ACCOUNTED).aggregate(s=Sum("shipping_price"))["s"] or Decimal("0"))
        ),
        "in_transit_product_preview": orders.filter(status=OrderStatus.IN_TRANSIT).aggregate(s=Sum("product_price"))["s"] or Decimal("0"),
        "in_transit_shipping_preview": orders.filter(status=OrderStatus.IN_TRANSIT).aggregate(s=Sum("shipping_price"))["s"] or Decimal("0"),
    }
    merchant_financials["remaining_due_after_under_account"] = (
        (merchant_financials["delivered_product_due"] - net_under_account).quantize(Decimal("0.01"))
    )

    return render(
        request,
        "merchants/merchant_detail.html",
        {
            "merchant": merchant,
            "page_obj": page_obj,
            "base_qs": base_qs,
            "bulk_form_id": "orders-bulk-form",
            "summary": summary,
            "payments": payments,
            "payments_summary": payments_summary,
            "payment_form": payment_form,
            "is_self_merchant": merchant.linked_user_id == request.user.id,
            "merchant_financials": merchant_financials,
            "net_under_account": net_under_account,
        },
    )


@login_required
def external_merchant_list(request):
    if not is_admin_level(request.user):
        messages.error(request, "غير مسموح.")
        return redirect("dashboard")
    query = query_first_str(request.GET, "q")
    merchants = Merchant.objects.filter(is_external=True)
    if query:
        merchants = merchants.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(address__icontains=query)
            | Q(brand_name__icontains=query)
        )
    merchants = merchants.annotate(
        total_orders=Count("orders", filter=Q(orders__external_waybill__isnull=False), distinct=True),
        delivered_orders=Count(
            "orders",
            filter=Q(orders__external_waybill__isnull=False, orders__status=OrderStatus.DELIVERED),
            distinct=True,
        ),
        in_transit_orders=Count(
            "orders",
            filter=Q(orders__external_waybill__isnull=False, orders__status=OrderStatus.IN_TRANSIT),
            distinct=True,
        ),
        accounted_orders=Count(
            "orders",
            filter=Q(orders__external_waybill__isnull=False, orders__status=OrderStatus.ACCOUNTED),
            distinct=True,
        ),
        delivered_product_total=Sum(
            "orders__product_price",
            filter=Q(orders__external_waybill__isnull=False, orders__status=OrderStatus.DELIVERED),
        ),
        delivered_shipping_total=Sum(
            "orders__shipping_price",
            filter=Q(orders__external_waybill__isnull=False, orders__status=OrderStatus.DELIVERED),
        ),
    ).order_by("name")
    paginator = Paginator(merchants, 24)
    page_obj = paginator.get_page(query_first_str(request.GET, "page") or 1)
    querystring = request.GET.copy()
    querystring.pop("page", None)
    base_qs = querystring.urlencode()
    return render(
        request,
        "merchants/merchant_list.html",
        {"page_obj": page_obj, "base_qs": base_qs, "external_mode": True},
    )


@login_required
def external_merchant_detail(request, merchant_id: int):
    merchant = get_object_or_404(Merchant, pk=merchant_id, is_external=True)
    if not is_admin_level(request.user):
        messages.error(request, "غير مسموح.")
        return redirect("dashboard")
    return merchant_detail(request, merchant.pk)
