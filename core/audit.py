from __future__ import annotations

from typing import Any

from .models import AuditLog


def log_action(request, action: str, obj: Any = None, message: str = "") -> None:
    user = None
    path = ""

    if request is not None:
        path = getattr(request, "path", "") or ""
        req_user = getattr(request, "user", None)
        if getattr(req_user, "is_authenticated", False):
            user = req_user

    model_name = obj.__class__.__name__ if obj is not None else ""
    object_id = str(getattr(obj, "pk", "") or "")
    object_repr = str(obj)[:255] if obj is not None else ""

    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        object_repr=object_repr,
        message=(message or "")[:255],
        path=path[:255],
    )

