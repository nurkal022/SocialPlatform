"""Weekly challenge logic."""
from django.db.models import Sum
from django.utils import timezone

from .models import WeeklyChallenge, XPLog


def current_challenge() -> WeeklyChallenge | None:
    today = timezone.now().date()
    return (
        WeeklyChallenge.objects
        .filter(starts_on__lte=today, ends_on__gte=today)
        .order_by("-starts_on")
        .first()
    )


def user_progress(user, challenge: WeeklyChallenge) -> dict:
    """Compute user's XP earned within the challenge date window."""
    if not user or not user.is_authenticated:
        return {"earned": 0, "target": challenge.target_xp, "pct": 0, "completed": False}

    earned = (
        XPLog.objects.filter(
            user=user,
            amount__gt=0,
            created_at__date__gte=challenge.starts_on,
            created_at__date__lte=challenge.ends_on,
        ).aggregate(s=Sum("amount"))["s"] or 0
    )
    earned = max(0, earned)
    pct = min(100, int(round(earned * 100 / challenge.target_xp))) if challenge.target_xp else 0
    return {
        "earned": earned,
        "target": challenge.target_xp,
        "pct": pct,
        "completed": earned >= challenge.target_xp,
    }
