"""مساعدات طلبات HTTP (قراءة QueryDict بشكل آمن للتحليل الثابت والوقت الفعلي)."""

from __future__ import annotations

from typing import Any

from django.http import QueryDict


def query_first_str(qd: QueryDict, key: str, default: str = "") -> str:
    """يعيد أول قيمة نصية لمفتاح (يدعم الحقول المتعددة بنفس الاسم)."""
    v: Any = qd.get(key, default)
    if v is None:
        return default
    if isinstance(v, (list, tuple)):
        v = v[0] if v else default
    return str(v).strip()


def query_first_value(qd: QueryDict, key: str, default: str = "") -> str:
    """مثل query_first_str بدون strip — مناسب لكلمة المرور."""
    v: Any = qd.get(key, default)
    if v is None:
        return default
    if isinstance(v, (list, tuple)):
        v = v[0] if v else default
    return str(v)
