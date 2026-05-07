from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DebtRepayment, UserProfile, UserRole

User = get_user_model()


@receiver(post_save, sender=User)
@receiver(post_save, sender=DebtRepayment)
def debt_repayment_refresh(sender, instance, created, **kwargs):
    debt = getattr(instance, "debt", None)
    if debt is not None:
        debt.refresh_payment_status()


def ensure_user_profile(sender, instance, created, **kwargs):
    """أي مستخدم جديد يحصل تلقائيًا على ملف صلاحيات."""
    if not created:
        return
    role = UserRole.SUPER_ADMIN if instance.is_superuser else UserRole.USER
    UserProfile.objects.get_or_create(user=instance, defaults={"role": role})
