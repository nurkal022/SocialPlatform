"""Studio — focused course/lesson editor for methodists, outside Django admin."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .models import Course, Lesson, Module


def _is_methodist(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


staff_required = user_passes_test(_is_methodist)


# ============================ DASHBOARD ============================

@login_required
@staff_required
def dashboard(request):
    courses = (
        Course.objects.all()
        .annotate(
            module_count=Count("modules", distinct=True),
            lesson_count=Count("modules__lessons", distinct=True),
            student_count=Count("enrollments", distinct=True),
        )
        .order_by("-is_published", "-updated_at")
    )
    return render(request, "studio/dashboard.html", {"courses": courses})


# ============================ COURSE ============================

@login_required
@staff_required
def course_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.warning(request, "Атауы бос болмауы керек.")
            return redirect("courses:studio_dashboard")
        slug = slugify(title) or f"course-{Course.objects.count() + 1}"
        # Ensure unique slug
        base = slug
        i = 1
        while Course.objects.filter(slug=slug).exists():
            i += 1
            slug = f"{base}-{i}"
        course = Course.objects.create(
            title=title, slug=slug,
            short_description="(толтыру керек)",
            description="(толтыру керек)",
            level=Course.Level.BEGINNER,
            language="kk",
            is_published=False,
            has_final_exam=False,
        )
        return redirect("courses:studio_course", slug=course.slug)
    return redirect("courses:studio_dashboard")


@login_required
@staff_required
def course_edit(request, slug):
    course = get_object_or_404(Course, slug=slug)
    modules = list(
        course.modules.all().prefetch_related("lessons").order_by("order")
    )
    return render(
        request,
        "studio/course.html",
        {"course": course, "modules": modules},
    )


@login_required
@staff_required
@require_POST
def course_update(request, slug):
    course = get_object_or_404(Course, slug=slug)
    field = request.POST.get("field")
    value = request.POST.get("value", "")
    allowed = {"title", "short_description", "description", "level", "language",
               "duration_hours", "tags", "is_published", "has_final_exam", "final_exam_pass_pct"}
    if field not in allowed:
        return JsonResponse({"ok": False, "error": "field not allowed"}, status=400)
    if field == "is_published" or field == "has_final_exam":
        value = value in ("1", "true", "on", "True")
    elif field in ("duration_hours", "final_exam_pass_pct"):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "bad number"}, status=400)
    setattr(course, field, value)
    course.save(update_fields=[field, "updated_at"])
    return JsonResponse({"ok": True, "value": value})


@login_required
@staff_required
@require_POST
def course_delete(request, slug):
    course = get_object_or_404(Course, slug=slug)
    title = course.title
    course.delete()
    messages.success(request, f"Курс «{title}» жойылды.")
    return redirect("courses:studio_dashboard")


# ============================ MODULE ============================

@login_required
@staff_required
@require_POST
def module_add(request, slug):
    course = get_object_or_404(Course, slug=slug)
    next_order = (course.modules.aggregate(m=__import__("django.db.models",
                  fromlist=["Max"]).Max("order"))["m"] or 0) + 1
    m = Module.objects.create(
        course=course,
        title=(request.POST.get("title") or f"Жаңа модуль {next_order}").strip(),
        order=next_order,
        has_test=False,
    )
    return JsonResponse({"ok": True, "id": m.id, "order": m.order, "title": m.title})


@login_required
@staff_required
@require_POST
def module_update(request, module_id):
    m = get_object_or_404(Module, pk=module_id)
    field = request.POST.get("field")
    value = request.POST.get("value", "")
    allowed = {"title", "summary", "has_test", "order"}
    if field not in allowed:
        return JsonResponse({"ok": False, "error": "field not allowed"}, status=400)
    if field == "has_test":
        value = value in ("1", "true", "on", "True")
    elif field == "order":
        try:
            value = int(value)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "bad number"}, status=400)
    setattr(m, field, value)
    m.save(update_fields=[field])
    return JsonResponse({"ok": True})


@login_required
@staff_required
@require_POST
def module_delete(request, module_id):
    m = get_object_or_404(Module, pk=module_id)
    course_slug = m.course.slug
    m.delete()
    return JsonResponse({"ok": True, "redirect": f"/studio/c/{course_slug}/"})


# ============================ LESSON ============================

@login_required
@staff_required
@require_POST
def lesson_add(request, module_id):
    m = get_object_or_404(Module, pk=module_id)
    next_order = (m.lessons.aggregate(n=__import__("django.db.models",
                  fromlist=["Max"]).Max("order"))["n"] or 0) + 1
    title = (request.POST.get("title") or f"Жаңа сабақ {next_order}").strip()
    base_slug = slugify(title) or f"lesson-{next_order}"
    slug = base_slug
    i = 1
    while m.lessons.filter(slug=slug).exists():
        i += 1
        slug = f"{base_slug}-{i}"
    lesson = Lesson.objects.create(
        module=m, title=title, slug=slug,
        order=next_order, content=[], duration_minutes=10,
    )
    return JsonResponse({
        "ok": True, "id": lesson.id, "order": lesson.order,
        "title": lesson.title, "url": f"/studio/l/{lesson.id}/",
    })


@login_required
@staff_required
def lesson_edit(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related("module__course"), pk=lesson_id
    )
    initial_json = json.dumps(lesson.content or [], ensure_ascii=False)
    return render(request, "studio/lesson.html", {
        "lesson": lesson, "initial_json": initial_json,
    })


@login_required
@staff_required
@require_POST
def lesson_update(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    # Handle both individual field updates and full content updates
    if request.POST.get("content_json"):
        try:
            content = json.loads(request.POST["content_json"])
            if not isinstance(content, list):
                return JsonResponse({"ok": False, "error": "content must be a list"}, status=400)
            lesson.content = content
            lesson.save(update_fields=["content", "updated_at"])
            return JsonResponse({"ok": True})
        except json.JSONDecodeError as e:
            return JsonResponse({"ok": False, "error": f"bad JSON: {e}"}, status=400)
    field = request.POST.get("field")
    value = request.POST.get("value", "")
    allowed = {"title", "summary", "duration_minutes", "video_url", "is_free_preview", "order"}
    if field not in allowed:
        return JsonResponse({"ok": False, "error": "field not allowed"}, status=400)
    if field == "is_free_preview":
        value = value in ("1", "true", "on", "True")
    elif field in ("duration_minutes", "order"):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "bad number"}, status=400)
    setattr(lesson, field, value)
    lesson.save(update_fields=[field, "updated_at"])
    return JsonResponse({"ok": True})


@login_required
@staff_required
@require_POST
def lesson_delete(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course_slug = lesson.module.course.slug
    lesson.delete()
    return JsonResponse({"ok": True, "redirect": f"/studio/c/{course_slug}/"})


# ============================ REORDER ============================

# ============================ QUIZ + QUESTIONS ============================

def _get_or_create_module_quiz(module):
    from assessments.models import Quiz
    quiz = Quiz.objects.filter(module=module, kind=Quiz.Kind.MODULE).first()
    if not quiz:
        quiz = Quiz.objects.create(
            course=module.course, module=module,
            kind=Quiz.Kind.MODULE,
            title=f"«{module.title}» модулінің тесті",
            description="",
            pass_pct=70, cooldown_minutes=30,
        )
    return quiz


def _get_or_create_final_quiz(course):
    from assessments.models import Quiz
    quiz = Quiz.objects.filter(course=course, kind=Quiz.Kind.FINAL).first()
    if not quiz:
        quiz = Quiz.objects.create(
            course=course, module=None,
            kind=Quiz.Kind.FINAL,
            title=f"«{course.title}» — финалдық емтихан",
            description="",
            pass_pct=70, time_limit_minutes=90, cooldown_minutes=24 * 60,
        )
    return quiz


def _quiz_to_initial(quiz):
    return {
        "id": quiz.id,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "explanation": q.explanation,
                "points": q.points,
                "choices": [c.text for c in q.choices.all()],
                "correct": next(
                    (i for i, c in enumerate(q.choices.all()) if c.is_correct), 0
                ),
            }
            for q in quiz.questions.prefetch_related("choices").order_by("order")
        ],
    }


@login_required
@staff_required
def quiz_module_edit(request, module_id):
    m = get_object_or_404(Module.objects.select_related("course"), pk=module_id)
    quiz = _get_or_create_module_quiz(m)
    if not m.has_test:
        m.has_test = True
        m.save(update_fields=["has_test"])
    return render(request, "studio/quiz.html", {
        "quiz": quiz, "kind_label": "Модуль тесті",
        "back_url": f"/courses/studio/c/{m.course.slug}/",
        "back_title": m.course.title,
        "scope_label": f"Модуль {m.order}: {m.title}",
        "initial_json": json.dumps(_quiz_to_initial(quiz), ensure_ascii=False),
    })


@login_required
@staff_required
def quiz_final_edit(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    quiz = _get_or_create_final_quiz(course)
    if not course.has_final_exam:
        course.has_final_exam = True
        course.save(update_fields=["has_final_exam"])
    return render(request, "studio/quiz.html", {
        "quiz": quiz, "kind_label": "Финалдық емтихан",
        "back_url": f"/courses/studio/c/{course.slug}/",
        "back_title": course.title,
        "scope_label": "Барлық модульдерді қамтиды",
        "initial_json": json.dumps(_quiz_to_initial(quiz), ensure_ascii=False),
    })


@login_required
@staff_required
@require_POST
def quiz_update(request, quiz_id):
    from assessments.models import Quiz
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    field = request.POST.get("field")
    value = request.POST.get("value", "")
    allowed = {"title", "description", "pass_pct", "time_limit_minutes",
               "cooldown_minutes", "question_count_override", "is_published"}
    if field not in allowed:
        return JsonResponse({"ok": False, "error": "field not allowed"}, status=400)
    if field == "is_published":
        value = value in ("1", "true", "on", "True")
    elif field in ("pass_pct", "time_limit_minutes", "cooldown_minutes", "question_count_override"):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "bad number"}, status=400)
    setattr(quiz, field, value)
    quiz.save(update_fields=[field])
    return JsonResponse({"ok": True})


@login_required
@staff_required
@require_POST
def question_add(request, quiz_id):
    from assessments.models import Quiz, Question, Choice
    from django.db.models import Max
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    next_order = (quiz.questions.aggregate(m=Max("order"))["m"] or 0) + 1
    q = Question.objects.create(
        quiz=quiz, kind=Question.Kind.SINGLE,
        text="Жаңа сұрақ", explanation="", points=1, order=next_order,
    )
    for i in range(4):
        Choice.objects.create(question=q, text=f"Вариант {i+1}",
                              is_correct=(i == 0), order=i + 1)
    return JsonResponse({
        "ok": True, "question": {
            "id": q.id, "text": q.text, "explanation": q.explanation, "points": q.points,
            "choices": [f"Вариант {i+1}" for i in range(4)], "correct": 0,
        },
    })


@login_required
@staff_required
@require_POST
@transaction.atomic
def question_update(request, question_id):
    from assessments.models import Question, Choice
    q = get_object_or_404(Question, pk=question_id)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)
    q.text = (data.get("text") or "").strip() or q.text
    q.explanation = data.get("explanation", "") or ""
    try:
        q.points = max(1, int(data.get("points", q.points)))
    except (TypeError, ValueError):
        pass
    q.save()
    if "choices" in data:
        choices = [c.strip() for c in data["choices"] if c and c.strip()]
        if len(choices) < 2:
            return JsonResponse({"ok": False, "error": "need at least 2 choices"}, status=400)
        correct_idx = int(data.get("correct", 0))
        correct_idx = max(0, min(len(choices) - 1, correct_idx))
        q.choices.all().delete()
        for i, ctext in enumerate(choices):
            Choice.objects.create(question=q, text=ctext,
                                  is_correct=(i == correct_idx), order=i + 1)
    return JsonResponse({"ok": True})


@login_required
@staff_required
@require_POST
def question_delete(request, question_id):
    from assessments.models import Question
    q = get_object_or_404(Question, pk=question_id)
    q.delete()
    return JsonResponse({"ok": True})


# ============================ REORDER ============================

@login_required
@staff_required
@require_POST
@transaction.atomic
def reorder(request):
    """Body: {kind: 'modules'|'lessons', ids: [id, id, ...]}"""
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)
    kind = data.get("kind")
    ids = data.get("ids") or []
    model = Module if kind == "modules" else Lesson if kind == "lessons" else None
    if not model:
        return JsonResponse({"ok": False, "error": "bad kind"}, status=400)
    for i, item_id in enumerate(ids, start=1):
        model.objects.filter(pk=item_id).update(order=i)
    return JsonResponse({"ok": True})
