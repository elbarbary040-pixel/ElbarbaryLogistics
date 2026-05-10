from django.urls import reverse

from orders.models import OrderStatus

from .models import ChatMessage, ChatThread, NotificationEvent, SiteAppearance
from .permissions import can_manage_staff_records, get_user_role, is_admin_level, is_super_admin


def site_branding(request):
    ctx = {
        "ORDER_STATUS_CHOICES": OrderStatus.choices,
        "site_appearance": None,
        "user_role": "",
        "is_super_admin": False,
        "is_admin_level": False,
        "can_manage_staff_records": False,
        "is_partner_user": False,
        "partner_home_url": "",
        "chat_unread_count": 0,
        "notifications_unread_count": 0,
    }
    try:
        ctx["site_appearance"] = SiteAppearance.load()
    except Exception:
        ctx["site_appearance"] = None
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return ctx
    ctx["user_role"] = get_user_role(request.user)
    ctx["is_super_admin"] = is_super_admin(request.user)
    ctx["is_admin_level"] = is_admin_level(request.user)
    ctx["can_manage_staff_records"] = can_manage_staff_records(request.user)
    try:
        merchant = request.user.merchant_profile
    except Exception:
        merchant = None
    try:
        delegate = request.user.delegate_profile
    except Exception:
        delegate = None
    if merchant is not None:
        ctx["is_partner_user"] = True
        ctx["partner_home_url"] = reverse("merchants:detail", kwargs={"merchant_id": merchant.pk})
    elif delegate is not None:
        ctx["is_partner_user"] = True
        ctx["partner_home_url"] = reverse("delegates:detail", kwargs={"delegate_id": delegate.pk})
    if ctx["is_admin_level"]:
        ctx["chat_unread_count"] = ChatMessage.objects.filter(read_at__isnull=True).exclude(sender=request.user).count()
    else:
        thread = ChatThread.objects.filter(participant=request.user).first()
        if thread:
            ctx["chat_unread_count"] = thread.messages.filter(read_at__isnull=True).exclude(sender=request.user).count()
    if ctx["is_admin_level"]:
        ctx["notifications_unread_count"] = NotificationEvent.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).count()
    return ctx
