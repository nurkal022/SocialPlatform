from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .models import Badge, Profile, Streak, UserBadge, XPLog


@transaction.atomic
def ensure_profile(user) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


@transaction.atomic
def ensure_streak(user) -> Streak:
    streak, _ = Streak.objects.get_or_create(user=user)
    return streak


@transaction.atomic
def award_xp(user, reason: str, amount: int, *, ref: str = ""):
    if not user or not user.is_authenticated:
        return None
    XPLog.objects.create(user=user, reason=reason, amount=amount, ref=ref)
    profile = ensure_profile(user)
    profile.xp = max(0, profile.xp + amount)
    profile.level = Profile.level_for_xp(profile.xp)

    today = timezone.now().date()
    if profile.last_week_reset != _week_start(today):
        profile.weekly_xp = 0
        profile.last_week_reset = _week_start(today)
    profile.weekly_xp += max(0, amount)
    if not profile.last_month_reset or profile.last_month_reset.month != today.month:
        profile.monthly_xp = 0
        profile.last_month_reset = today.replace(day=1)
    profile.monthly_xp += max(0, amount)
    profile.save()

    _touch_streak(user)
    _check_badges(user)
    return profile


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


@transaction.atomic
def _touch_streak(user):
    streak = ensure_streak(user)
    today = timezone.now().date()
    if streak.month_marker is None or streak.month_marker.month != today.month:
        streak.freezes_used_month = 0
        streak.month_marker = today.replace(day=1)

    if streak.last_activity_date == today:
        streak.save()
        return streak
    if streak.last_activity_date is None:
        streak.current = 1
    else:
        gap = (today - streak.last_activity_date).days
        if gap == 1:
            streak.current += 1
        elif gap == 2 and streak.freezes_available > 0:
            streak.freezes_available -= 1
            streak.freezes_used_month += 1
            streak.current += 1
        else:
            streak.current = 1
    streak.longest = max(streak.longest, streak.current)
    streak.last_activity_date = today
    streak.save()

    if streak.current % 7 == 0:
        award_xp(user, "streak_week", 25, ref=f"streak:{streak.current}")
    return streak


def _check_badges(user):
    profile = ensure_profile(user)
    streak = ensure_streak(user)
    from courses.models import LessonProgress, Enrollment
    from assessments.models import Attempt, CaseSubmission

    metrics = {
        "lessons_completed": LessonProgress.objects.filter(
            user=user, completed_at__isnull=False
        ).count(),
        "xp_total": profile.xp,
        "streak_days": streak.current,
        "cases_graded": CaseSubmission.objects.filter(
            user=user, status=CaseSubmission.Status.GRADED
        ).count(),
        "quizzes_passed": Attempt.objects.filter(
            user=user, status=Attempt.Status.SUBMITTED, score_pct__gte=70
        ).count(),
        "courses_finished": Enrollment.objects.filter(
            user=user, completed_at__isnull=False
        ).count(),
    }
    owned = set(UserBadge.objects.filter(user=user).values_list("badge_id", flat=True))
    for badge in Badge.objects.all():
        if badge.id in owned:
            continue
        value = metrics.get(badge.rule, 0)
        if value >= badge.threshold:
            UserBadge.objects.get_or_create(user=user, badge=badge)
            XPLog.objects.create(
                user=user, reason="badge", amount=50, ref=f"badge:{badge.code}"
            )


def leaderboard(scope: str = "all", *, university=None, region=None, limit: int = 20):
    qs = Profile.objects.select_related("user")
    if university:
        qs = qs.filter(user__university=university)
    if region:
        qs = qs.filter(user__region=region)
    if scope == "weekly":
        qs = qs.order_by("-weekly_xp")
    elif scope == "monthly":
        qs = qs.order_by("-monthly_xp")
    else:
        qs = qs.order_by("-xp")
    return qs[:limit]


DEFAULT_BADGES = [
    # rule, code, name, icon, threshold, tier, description
    ("lessons_completed", "shakirt", "Шәкірт", "🌱", 1, 1, "Алғашқы сабақты аяқтады"),
    ("lessons_completed", "izdenushi", "Ізденуші", "📘", 10, 2, "10 сабақты аяқтады"),
    ("lessons_completed", "zertteushi", "Зерттеуші", "🔬", 30, 3, "30 сабақты аяқтады"),
    ("lessons_completed", "tarbieshi", "Тәрбиеші", "🌿", 60, 3, "60 сабақты аяқтады"),
    ("lessons_completed", "didakt", "Дидакт", "🎓", 100, 4, "100 сабақты аяқтады"),
    ("xp_total", "xp_500", "500 XP", "⭐", 500, 1, "500 XP жинады"),
    ("xp_total", "xp_2000", "2000 XP", "✨", 2000, 2, "2000 XP жинады"),
    ("xp_total", "xp_5000", "5000 XP", "🌟", 5000, 3, "5000 XP жинады"),
    ("xp_total", "xp_10000", "10000 XP", "💫", 10000, 4, "10000 XP жинады"),
    ("streak_days", "streak_3", "3 күн қатарынан", "🔥", 3, 1, "3 күн streak"),
    ("streak_days", "streak_7", "Апта қатарынан", "🔥🔥", 7, 2, "7 күн streak"),
    ("streak_days", "streak_30", "Ай қатарынан", "🔥🔥🔥", 30, 3, "30 күн streak"),
    ("streak_days", "streak_100", "Жүз күн", "🌋", 100, 4, "100 күн streak"),
    ("cases_graded", "case_first", "Алғашқы кейс", "📝", 1, 1, "Алғашқы кейсті тапсырды"),
    ("cases_graded", "case_5", "Тәжірибелі", "📂", 5, 2, "5 кейсті тапсырды"),
    ("cases_graded", "case_15", "Тәлімгер", "🧑‍🏫", 15, 3, "15 кейсті тапсырды"),
    ("cases_graded", "case_30", "Шебер педагог", "🏆", 30, 4, "30 кейсті тапсырды"),
    ("quizzes_passed", "quiz_first", "Тест жеңімпазы", "✅", 1, 1, "Алғашқы тестті тапсырды"),
    ("quizzes_passed", "quiz_10", "Тестмейстер", "🎯", 10, 2, "10 тестті тапсырды"),
    ("quizzes_passed", "quiz_30", "Білімпаз", "💎", 30, 3, "30 тестті тапсырды"),
    ("courses_finished", "course_first", "Курс бітірген", "🎓", 1, 3, "Алғашқы курсты аяқтады"),
    ("courses_finished", "course_3", "Полимат", "🏛️", 3, 4, "3 курсты аяқтады"),
]


def seed_default_badges():
    created = 0
    for rule, code, name, icon, thr, tier, desc in DEFAULT_BADGES:
        _, was_created = Badge.objects.update_or_create(
            code=code,
            defaults=dict(
                name=name, icon=icon, threshold=thr, tier=tier, rule=rule, description=desc
            ),
        )
        if was_created:
            created += 1
    return created
