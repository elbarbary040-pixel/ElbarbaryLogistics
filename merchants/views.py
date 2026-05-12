ffrom django.contrib import messages
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

_ORDER_STATUS_CODES = [c for c, _ in OrderStatus.choices]

@login_required
def merchant_list(request):
    if not is_admin_level(request.user):
        own = Merchant.objects.filter(linked_user=request.user).first()
        if own:
            return redirect("merchants:detail", merchant_id=own.pk)

    q = query_first_str(request.GET, "q")

    merchants = Merchant.objects.all()

    if q:
        merchants = merchants.filter(
            Q(name__icontains=q)
            | Q(phone__icontains=q)
            | Q(address__icontains=q)
            | Q(brand_name__icontains=q)
        )

    merchants = merchants.annotate(
        total_orders=Count("orders", distinct=True),
        delivered_orders=Count("orders", filter=Q(orders__status=OrderStatus.DELIVERED), distinct=True),
        in_transit_orders=Count("orders", filter=Q(orders__status=OrderStatus.IN_TRANSIT), distinct=True),
        accounted_orders=Count("orders", filter=Q(orders__status=OrderStatus.ACCOUNTED), distinct=True),
        delivered_product_total=Sum("orders__product_price"),
        delivered_shipping_total=Sum("orders__shipping_price"),
    ).order_by("name")

    paginator = Paginator(merchants, 24)
    page_obj = paginator.get_page(query_first_str(request.GET, "page") or 1)

    qs = request.GET.copy()
    qs.pop("page", None)

    return render(request, "merchants/merchant_list.html", {
        "page_obj": page_obj,
        "base_qs": qs.urlencode(),
    })
@login_required
def merchant_add(request):
    form = MerchantForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        merchant = form.save()
        log_action(request, AuditAction.CREATE, merchant, "إضافة تاجر")
        messages.success(request, f"تم إضافة التاجر: {merchant.name}")
        return redirect("merchants:detail", merchant_id=merchant.id)

    return render(request, "merchants/merchant_form.html", {"form": form})

@@login_required
def merchant_edit(request, merchant_id):
    if not can_manage_staff_records(request.user):
        messages.error(request, "لا صلاحية.")
        return redirect("dashboard")

    merchant = get_object_or_404(Merchant, pk=merchant_id)
    linked = merchant.linked_user

    form = MerchantForm(request.POST or None, instance=merchant)
    user_form = UserEditForm(request.POST or None, instance=linked) if linked else None

    if request.method == "POST":
        if request.POST.get("save_linked_user") == "1" and linked:
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "تم تحديث المستخدم.")
                return redirect(request.path)

        else:
            if form.is_valid():
                form.save()
                messages.success(request, "تم حفظ التاجر.")
                return redirect("merchants:detail", merchant_id=merchant.id)

    return render(request, "merchants/merchant_edit.html", {
        "form": form,
        "merchant": merchant,
        "user_form": user_form,
        "linked_user": linked,
    })
@login_required
def merchant_soft_delete(request, merchant_id):
    if not can_manage_staff_records(request.user):
        messages.error(request, "غير مسموح.")
        return redirect("merchants:list")

    merchant = get_object_or_404(Merchant, pk=merchant_id)

    if request.method == "POST":
        merchant.soft_delete(request.user)
        messages.success(request, "تم حذف التاجر.")
    
    return redirect("merchants:list")
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
