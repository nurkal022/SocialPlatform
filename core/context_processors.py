from django.conf import settings
from django.contrib.auth import get_user_model


def platform(request):
    ctx = {
        "PLATFORM_NAME": "Ұстаз",
        "PLATFORM_TAGLINE": "Болашақ ұстаздар үшін цифрлық академия",
        "DEBUG": settings.DEBUG,
        "IMPERSONATING": False,
        "IMPERSONATOR": None,
        "ROLE_SWITCHER_USERS": [],
    }
    User = get_user_model()
    original_id = request.session.get("impersonate_original_id") if hasattr(request, "session") else None
    if original_id:
        ctx["IMPERSONATING"] = True
        ctx["IMPERSONATOR"] = User.objects.filter(pk=original_id).first()

    user = getattr(request, "user", None)
    can_switch = user and user.is_authenticated and (user.is_staff or user.is_superuser or ctx["IMPERSONATING"])
    if settings.DEBUG and can_switch:
        ctx["ROLE_SWITCHER_USERS"] = list(
            User.objects.filter(
                username__in=["admin", "metodist", "student", "aigerim", "beginner"]
            ).order_by("username")
        )
    return ctx
