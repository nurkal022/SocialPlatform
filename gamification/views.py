from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Badge, UserBadge
from .services import ensure_profile, ensure_streak, leaderboard


def leaderboard_view(request):
    scope = request.GET.get("scope", "all")
    scope_kind = request.GET.get("kind", "global")  # global|university|region
    university = region = None
    if scope_kind == "university" and request.user.is_authenticated:
        university = request.user.university
    elif scope_kind == "region" and request.user.is_authenticated:
        region = request.user.region
    rows = leaderboard(scope=scope, university=university, region=region, limit=50)
    return render(
        request,
        "gamification/leaderboard.html",
        {"rows": rows, "scope": scope, "scope_kind": scope_kind},
    )


def badges_index(request):
    badges = Badge.objects.all()
    owned_ids = set()
    if request.user.is_authenticated:
        owned_ids = set(
            UserBadge.objects.filter(user=request.user).values_list("badge_id", flat=True)
        )
    return render(
        request, "gamification/badges.html",
        {"badges": badges, "owned_ids": owned_ids},
    )


@login_required
def my_progress(request):
    profile = ensure_profile(request.user)
    streak = ensure_streak(request.user)
    badges = UserBadge.objects.filter(user=request.user).select_related("badge")
    into, total_for_level = profile.xp_into_level()
    return render(
        request, "gamification/me.html",
        {
            "profile": profile, "streak": streak, "badges": badges,
            "into_level": into, "total_for_level": total_for_level,
            "pct_to_next": int(round(into * 100 / total_for_level)) if total_for_level else 0,
        },
    )
