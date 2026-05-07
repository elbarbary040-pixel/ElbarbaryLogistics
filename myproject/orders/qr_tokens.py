"""توكن مشفَّر لفتح الطلب بواسطة الماسح (مع صلاحية المستخدم وتسجيل الدخول)."""

from django.core.signing import BadSignature, Signer

SIGNER = Signer(salt="internal-order-scan-v1")


def sign_order_pk(pk: int) -> str:
    return SIGNER.sign(str(pk))


def unsign_order_token(token: str) -> int | None:
    raw = (token or "").strip()
    if not raw:
        return None
    try:
        plain = SIGNER.unsign(raw)
        return int(plain)
    except (BadSignature, ValueError, OverflowError):
        return None
