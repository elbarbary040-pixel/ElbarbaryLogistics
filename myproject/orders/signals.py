from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Order, OrderStatus, OrderStatusHistory
from .services.accounting import apply_status_accounting


@receiver(pre_save, sender=Order)
def order_cache_previous_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._prev_status = (
                Order.objects.only("status").get(pk=instance.pk).status
            )
        except Order.DoesNotExist:
            instance._prev_status = None
    else:
        instance._prev_status = None


@receiver(post_save, sender=Order)
def order_after_save(sender, instance, created, **kwargs):
    old = getattr(instance, "_prev_status", None)
    new = instance.status
    if not created and (old or "") == (new or ""):
        return
    if created and new == OrderStatus.IN_TRANSIT:
        return
    user = getattr(instance, "_save_user", None)
    OrderStatusHistory.objects.create(
        order=instance,
        old_status=(old or ""),
        new_status=new,
        changed_by=user if user and getattr(user, "is_authenticated", False) else None,
    )
    apply_status_accounting(instance, old, new, user)
