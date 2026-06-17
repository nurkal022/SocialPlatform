from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Course, Enrollment, Lesson, LessonProgress, Note


def catalog(request):
    from django.db.models import Avg
    q = request.GET.get("q", "").strip()
    level = request.GET.get("level", "")
    lang = request.GET.get("lang", "")
    sort = request.GET.get("sort", "popular")
    courses = Course.objects.filter(is_published=True).annotate(
        lesson_count=Count("modules__lessons"),
        student_count=Count("enrollments", distinct=True),
        avg_rating=Avg("reviews__rating"),
    )
    if q:
        courses = courses.filter(
            Q(title__icontains=q)
            | Q(short_description__icontains=q)
            | Q(description__icontains=q)
            | Q(tags__icontains=q)
        )
    if level:
        courses = courses.filter(level=level)
    if lang:
        courses = courses.filter(language=lang)

    sort_map = {
        "newest": "-created_at",
        "popular": "-student_count",
        "rating": "-avg_rating",
        "shortest": "duration_hours",
    }
    courses = courses.order_by(sort_map.get(sort, "-student_count"))

    return render(
        request,
        "courses/catalog.html",
        {
            "courses": courses,
            "q": q,
            "level": level,
            "lang": lang,
            "sort": sort,
            "levels": Course.Level.choices,
        },
    )


def detail(request, slug):
    course = get_object_or_404(
        Course.objects.prefetch_related("modules__lessons", "modules__cases", "authors"),
        slug=slug,
        is_published=True,
    )
    enrollment = None
    if request.user.is_authenticated:
        enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
    completed_lesson_ids = set()
    if enrollment:
        completed_lesson_ids = set(
            LessonProgress.objects.filter(
                user=request.user,
                lesson__module__course=course,
                completed_at__isnull=False,
            ).values_list("lesson_id", flat=True)
        )

    # Reviews
    from social.models import CourseReview
    from django.db.models import Avg, Count
    reviews = list(
        CourseReview.objects.filter(course=course)
        .select_related("user")
        .order_by("-created_at")[:20]
    )
    review_stats = CourseReview.objects.filter(course=course).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    my_review = None
    if request.user.is_authenticated:
        my_review = CourseReview.objects.filter(course=course, user=request.user).first()

    return render(
        request,
        "courses/detail.html",
        {
            "course": course,
            "enrollment": enrollment,
            "completed_lesson_ids": completed_lesson_ids,
            "reviews": reviews,
            "review_avg": review_stats["avg"],
            "review_count": review_stats["count"],
            "my_review": my_review,
        },
    )


@login_required
def enroll(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)
    Enrollment.objects.get_or_create(user=request.user, course=course)
    messages.success(request, f"Сіз «{course.title}» курсына жазылдыңыз!")
    first_lesson = Lesson.objects.filter(module__course=course).order_by("module__order", "order").first()
    if first_lesson:
        return redirect(first_lesson.get_absolute_url())
    return redirect(course.get_absolute_url())


@login_required
def lesson_view(request, course_slug, module_id, lesson_slug):
    lesson = get_object_or_404(
        Lesson.objects.select_related("module__course"),
        module__course__slug=course_slug,
        module_id=module_id,
        slug=lesson_slug,
    )
    course = lesson.module.course
    enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
    if not enrollment and not lesson.is_free_preview:
        messages.info(request, "Алдымен курсқа жазылыңыз.")
        return redirect("courses:detail", slug=course.slug)

    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)
    note = Note.objects.filter(user=request.user, lesson=lesson).first()

    lessons_ordered = list(
        Lesson.objects.filter(module__course=course).order_by("module__order", "order")
    )
    try:
        idx = next(i for i, ln in enumerate(lessons_ordered) if ln.id == lesson.id)
    except StopIteration:
        idx = 0
    prev_lesson = lessons_ordered[idx - 1] if idx > 0 else None
    next_lesson = lessons_ordered[idx + 1] if idx + 1 < len(lessons_ordered) else None

    # Full course tree for sidebar
    modules = list(course.modules.all().prefetch_related("lessons", "cases"))

    # Lesson comments (top-level + replies)
    from social.models import Comment
    comments = list(
        Comment.objects.filter(lesson=lesson, is_hidden=False, parent__isnull=True)
        .select_related("user")
        .prefetch_related("replies__user", "likes")
        .order_by("-created_at")[:50]
    )
    completed_lesson_ids = set(
        LessonProgress.objects.filter(
            user=request.user,
            lesson__module__course=course,
            completed_at__isnull=False,
        ).values_list("lesson_id", flat=True)
    )

    # Group blocks into steps: a "step" is a sequence of content blocks
    # broken on each `question` block (questions are their own steps).
    steps = []
    current: list = []
    for block in (lesson.content or []):
        btype = block.get("type") if isinstance(block, dict) else None
        if btype == "question":
            if current:
                steps.append({"kind": "content", "blocks": current})
                current = []
            steps.append({"kind": "question", "blocks": [block]})
        else:
            current.append(block)
    if current:
        steps.append({"kind": "content", "blocks": current})
    if not steps:
        steps.append({"kind": "content", "blocks": []})

    return render(
        request,
        "courses/lesson.html",
        {
            "lesson": lesson,
            "course": course,
            "module": lesson.module,
            "modules": modules,
            "completed_lesson_ids": completed_lesson_ids,
            "progress": progress,
            "note": note,
            "prev_lesson": prev_lesson,
            "next_lesson": next_lesson,
            "is_completed": progress.completed_at is not None,
            "steps": steps,
            "step_count": len(steps),
            "comments": comments,
        },
    )


@login_required
@require_POST
def complete_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)
    just_completed_course = False
    if not progress.completed_at:
        progress.completed_at = timezone.now()
        progress.save()
        from gamification.services import award_xp
        award_xp(request.user, "lesson_complete", 10, ref=f"lesson:{lesson.id}")

        # Check if this was the last lesson of the course
        course = lesson.module.course
        total = Lesson.objects.filter(module__course=course).count()
        done = LessonProgress.objects.filter(
            user=request.user, lesson__module__course=course, completed_at__isnull=False
        ).count()
        if total and done == total:
            # Mark enrollment as 100% lessons done (final exam still separate)
            enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
            if enrollment and not enrollment.completed_at and not course.has_final_exam:
                enrollment.completed_at = timezone.now()
                enrollment.save()
            just_completed_course = True
            # Persist a flash via session for the next page
            request.session["completed_course_id"] = course.id

    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<span class="completed-badge">✓ Аяқталды</span>',
            content_type="text/html",
        )
    return redirect(lesson.get_absolute_url())


@login_required
@require_POST
def save_note(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    body = request.POST.get("body", "").strip()
    if body:
        Note.objects.update_or_create(
            user=request.user, lesson=lesson, defaults={"body": body}
        )
        return JsonResponse({"ok": True, "saved_at": timezone.now().isoformat()})
    return JsonResponse({"ok": False}, status=400)
