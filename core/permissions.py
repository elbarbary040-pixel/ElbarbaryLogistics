"""صلاحيات الأدوار: مدير عام، مسؤول، مستخدم."""

from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest

from .models import UserRole


def get_user_role(user) -> str:
    if not user.is_authenticated:
        return ""
    if getattr(user, "is_superuser", False):
        return UserRole.SUPER_ADMIN
    profile = getattr(user, "profile", None)
    if profile:
        return profile.role
    return UserRole.USER


def is_super_admin(user) -> bool:
    return get_user_role(user) == UserRole.SUPER_ADMIN


def is_admin_level(user) -> bool:
    return get_user_role(user) in {UserRole.SUPER_ADMIN, UserRole.ADMIN}


def can_manage_staff_records(user) -> bool:
    """
    بحث / تعديل / حذف السجلات (شحنات، تجار، مندوبين، مستخدمين) — للموظفين فقط
    (مستخدم / مسؤول / مدير عام)، لا يشمل التاجر والمندوب (الشركاء).
    """
    if not user.is_authenticated:
        return False
    return get_user_role(user) in {UserRole.USER, UserRole.ADMIN, UserRole.SUPER_ADMIN}


def orders_queryset_for_user(user):
    from orders.models import Order

    qs = Order.objects.select_related("merchant", "delegate").all()
    if not user.is_authenticated:
        return qs.none()
    try:
        merchant = user.merchant_profile
    except Exception:
        merchant = None
    if merchant is not None:
        return qs.filter(merchant=merchant)
    try:
        delegate = user.delegate_profile
    except Exception:
        delegate = None
    if delegate is not None:
        return qs.filter(delegate=delegate)
    return qs


def require_roles(*roles: str):
    """Decorator: يسمح فقط بالأدوار المذكورة (قيم UserRole)."""

    def decorator(view_func):
        def _wrapped(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), "login", REDIRECT_FIELD_NAME)
            if get_user_role(request.user) not in roles:
                from django.contrib import messages
                from django.shortcuts import redirect

                messages.error(request, "ليس لديك صلاحية لهذه الصفحة.")
                return redirect("dashboard")
            return view_func(request, *args, **kwargs)

        return wraps(view_func)(_wrapped)

    return decorator
