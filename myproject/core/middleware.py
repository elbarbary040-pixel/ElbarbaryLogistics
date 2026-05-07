from uuid import uuid4
import traceback

from django.contrib import messages
from django.shortcuts import redirect

from .models import AppErrorLog, AuditAction, AuditLog, ClientSession


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45] or None


class ClientSessionMiddleware:
    """يحدّث آخر ظهور للمستخدم (أساس صفحة الأجهزة)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return response
        path = request.path or ""
        if path.startswith("/static/") or path.startswith("/media/"):
            return response
        key = request.session.get("_device_uid")
        if not key:
            key = str(uuid4())
            request.session["_device_uid"] = key
        ClientSession.objects.update_or_create(
            user=request.user,
            device_label=key[:120],
            defaults={
                "ip_address": _client_ip(request),
                "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:512],
            },
        )
        return response


class PartnerAccessControlMiddleware:
    """
    يمنع حسابات التاجر/المندوب من الوصول لأي صفحات إدارية يدويًا.
    المسموح لهم فقط:
    - صفحتهم الشخصية
    - الشات
    - طلب شحنة
    - الخروج (والداشبورد لإعادة التوجيه)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        try:
            merchant = user.merchant_profile
        except Exception:
            merchant = None
        try:
            delegate = user.delegate_profile
        except Exception:
            delegate = None

        if merchant is None and delegate is None:
            return self.get_response(request)

        path = request.path or "/"
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        partner_home = (
            f"/merchants/{merchant.pk}/"
            if merchant is not None
            else f"/delegates/{delegate.pk}/"
        )
        allowed_prefixes = {
            "/logout/",
            "/chat/",
            "/order-request/new/",
            "/orders/scanner/",
            "/orders/lookup/",
            "/dashboard/",
            partner_home,
        }

        if any(path.startswith(p) for p in allowed_prefixes):
            return self.get_response(request)

        messages.error(request, "غير مسموح لك بدخول هذه الصفحة.")
        return redirect(partner_home)


class AuditTrailMiddleware:
    """يسجل كل العمليات غير GET تلقائيًا في سجل العمليات."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                user = request.user if getattr(request.user, "is_authenticated", False) else None
                AuditLog.objects.create(
                    user=user,
                    action=AuditAction.OTHER,
                    model_name="Request",
                    object_id="",
                    object_repr=request.method,
                    message=f"HTTP {request.method} {request.path}",
                    path=(request.path or "")[:255],
                    extra={"status_code": getattr(response, "status_code", None)},
                )
            except Exception:
                pass
        return response


class ExceptionCaptureMiddleware:
    """يحفظ أي خطأ غير معالج في قاعدة البيانات لصفحة أخطاء السوبر أدمن."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            try:
                AppErrorLog.objects.create(
                    user=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
                    path=(request.path or "")[:255],
                    error_type=exc.__class__.__name__[:120],
                    message=str(exc),
                    traceback_text=traceback.format_exc()[:20000],
                )
            except Exception:
                pass
            raise
