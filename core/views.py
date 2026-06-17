from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import redirect, render

from courses.models import Course, LessonProgress
from gamification.models import XPLog


def landing(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    courses = Course.objects.filter(is_published=True).annotate(
        lesson_count=Count("modules__lessons"),
        student_count=Count("enrollments", distinct=True),
    )[:6]
    return render(request, "core/landing.html", {"courses": courses})


@login_required
def dashboard(request):
    user = request.user
    enrollments = list(
        user.enrollments.select_related("course")
        .prefetch_related("course__modules__lessons")
        .all()
    )

    # Build per-module progress for each enrollment
    completed_lesson_ids = set(
        LessonProgress.objects.filter(user=user, completed_at__isnull=False)
        .values_list("lesson_id", flat=True)
    )
    enrollment_details = []
    for e in enrollments:
        modules_progress = []
        for m in e.course.modules.all():
            lesson_ids = list(m.lessons.values_list("id", flat=True))
            done = sum(1 for lid in lesson_ids if lid in completed_lesson_ids)
            modules_progress.append({
                "module": m,
                "done": done,
                "total": len(lesson_ids),
                "pct": int(round(done * 100 / len(lesson_ids))) if lesson_ids else 0,
            })
        enrollment_details.append({
            "enrollment": e,
            "modules": modules_progress,
            "overall_pct": e.progress_pct(),
        })

    recent_lessons = (
        LessonProgress.objects.filter(user=user, completed_at__isnull=False)
        .select_related("lesson__module__course")
        .order_by("-completed_at")[:5]
    )
    xp_today = (
        XPLog.objects.filter(user=user, created_at__date=user.date_joined.date())
        .aggregate(s=Sum("amount"))["s"]
        or 0
    )

    # Weekly challenge
    from gamification.services_challenges import current_challenge, user_progress
    challenge = current_challenge()
    challenge_progress = user_progress(user, challenge) if challenge else None

    # Suggested course for empty-dashboard CTA
    from courses.models import Course
    enrolled_course_ids = {e.course_id for e in enrollments}
    suggested = (
        Course.objects.filter(is_published=True)
        .exclude(id__in=enrolled_course_ids)
        .first()
    )

    # Recently earned badges (for toast)
    from gamification.models import UserBadge
    from django.utils import timezone
    from datetime import timedelta
    recent_badges = list(
        UserBadge.objects.filter(user=user, awarded_at__gte=timezone.now() - timedelta(minutes=5))
        .select_related("badge")
    )

    # Course-completion celebration (set by complete_lesson when last lesson done)
    just_completed_course = None
    completed_id = request.session.pop("completed_course_id", None)
    if completed_id:
        from courses.models import Course
        just_completed_course = Course.objects.filter(id=completed_id).first()

    return render(
        request,
        "core/dashboard.html",
        {
            "enrollments": enrollments,
            "enrollment_details": enrollment_details,
            "recent_lessons": recent_lessons,
            "xp_today": xp_today,
            "challenge": challenge,
            "challenge_progress": challenge_progress,
            "suggested": suggested,
            "recent_badges": recent_badges,
            "just_completed_course": just_completed_course,
        },
    )


def about(request):
    from courses.models import Course, Lesson
    from assessments.models import CaseStudy, Question
    stats = {
        "courses": Course.objects.filter(is_published=True).count(),
        "lessons": Lesson.objects.count(),
        "cases": CaseStudy.objects.count(),
        "questions": Question.objects.count(),
    }
    return render(request, "core/about.html", {"stats": stats})


def healthz(request):
    """Cheap health endpoint for monitors. Checks DB connectivity."""
    from django.db import connection
    from django.http import JsonResponse
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)[:200]}, status=503)
