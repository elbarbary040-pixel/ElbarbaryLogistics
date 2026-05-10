from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import NotificationEvent, UserRole


def notify_admin_users(title: str, body: str = "", link_url: str = "") -> int:
    """ينشئ إشعارات قراءة داخل لوحة الموظفين (مدير نظام أو مسؤول)."""

    User = get_user_model()
    qs = (
        User.objects.filter(is_active=True)
        .filter(
            Q(is_superuser=True) | Q(profile__role__in={UserRole.SUPER_ADMIN, UserRole.ADMIN}),
        )
        .distinct()
    )
    n = 0
    for user in qs:
        NotificationEvent.objects.create(
            user=user,
            title=title[:200],
            body=body[:5000],
            link_url=(link_url or "")[:512],
            channel=NotificationEvent.Channel.IN_APP,
        )
        n += 1
    return n
