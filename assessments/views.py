import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .grading import grade_attempt
from .models import Attempt, CaseStudy, CaseSubmission, Quiz


def cases_catalog(request):
    qs = CaseStudy.objects.filter(is_published=True).select_related("course", "module")
    course_slug = request.GET.get("course")
    difficulty = request.GET.get("difficulty")
    if course_slug:
        qs = qs.filter(course__slug=course_slug)
    if difficulty:
        qs = qs.filter(difficulty=difficulty)
    return render(request, "assessments/cases_catalog.html", {"cases": qs})


@login_required
def case_detail(request, case_id):
    case = get_object_or_404(
        CaseStudy.objects.select_related("course", "module"),
        pk=case_id, is_published=True,
    )
    submission = (
        CaseSubmission.objects.filter(case=case, user=request.user)
        .order_by("-submitted_at")
        .first()
    )

    # Build sidebar context (same as lesson view) so navigation feels seamless
    course = case.course
    modules = list(
        course.modules.all().prefetch_related("lessons", "cases")
    ) if course else []
    from courses.models import Enrollment, LessonProgress
    completed_lesson_ids = set()
    enrollment = None
    if course:
        enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
        completed_lesson_ids = set(
            LessonProgress.objects.filter(
                user=request.user,
                lesson__module__course=course,
                completed_at__isnull=False,
            ).values_list("lesson_id", flat=True)
        )

    # Where to go back: explicit ?from=lesson_id, else previous lesson in same module
    from courses.models import Lesson
    return_to = None
    from_lesson = request.GET.get("from")
    if from_lesson and from_lesson.isdigit():
        return_to = Lesson.objects.filter(id=int(from_lesson), module__course=course).first()
    if not return_to and case.module:
        return_to = case.module.lessons.first()

    return render(
        request,
        "assessments/case_detail.html",
        {
            "case": case,
            "submission": submission,
            "rubric": case.default_rubric(),
            "course": course,
            "modules": modules,
            "completed_lesson_ids": completed_lesson_ids,
            "enrollment": enrollment,
            "return_to": return_to,
        },
    )


@login_required
@require_POST
def case_submit(request, case_id):
    case = get_object_or_404(CaseStudy, pk=case_id, is_published=True)
    body = (request.POST.get("response") or "").strip()
    words = len(body.split())
    if words < case.min_words:
        messages.warning(
            request,
            f"Жауап тым қысқа: {words} сөз. Кемінде {case.min_words} сөз қажет.",
        )
        return redirect("assessments:case_detail", case_id=case.id)

    submission = CaseSubmission.objects.create(
        case=case, user=request.user, response=body, status=CaseSubmission.Status.DRAFT
    )

    # Try AI grading; gracefully fall back if not configured.
    from aitutor.services import grade_case_submission, AIServiceUnavailable, AIRateLimited
    try:
        result = grade_case_submission(case, body, user=request.user)
        submission.score = int(result.get("score", 0))
        submission.criteria_scores = result.get("criteria", [])
        submission.feedback = result.get("feedback", "")
        submission.status = CaseSubmission.Status.GRADED
        submission.graded_at = timezone.now()
        submission.save()
        from gamification.services import award_xp
        award_xp(request.user, "case_grade", min(100, max(50, submission.score)), ref=f"case:{case.id}")
        messages.success(request, f"ИИ бағалады: {submission.score}/100")
    except AIRateLimited as e:
        submission.status = CaseSubmission.Status.FAILED
        submission.feedback = f"Күндік лимиттен астыңыз: {e}"
        submission.save()
        messages.warning(request, "Бүгінгі ИИ-бағалау лимитінен астыңыз. Ертең қайталап көріңіз.")
    except AIServiceUnavailable as e:
        submission.status = CaseSubmission.Status.FAILED
        submission.feedback = f"ИИ-қызметі қолжетімсіз: {e}"
        submission.save()
        messages.warning(request, "ИИ қызметі әзірге қолжетімсіз. Жауабыңыз сақталды.")

    return redirect("assessments:case_detail", case_id=case.id)


# ---------- QUIZZES ----------


@login_required
def quiz_start(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id, is_published=True)
    # Cooldown
    last = Attempt.objects.filter(user=request.user, quiz=quiz).order_by("-started_at").first()
    if last and last.status != Attempt.Status.IN_PROGRESS:
        elapsed_min = (timezone.now() - last.started_at).total_seconds() / 60
        if elapsed_min < quiz.cooldown_minutes:
            wait_min = int(quiz.cooldown_minutes - elapsed_min)
            ready_at = last.started_at + timezone.timedelta(minutes=quiz.cooldown_minutes)
            messages.warning(
                request,
                f"Келесі әрекетке дейін {wait_min} минут күтіңіз "
                f"({ready_at:%d.%m %H:%M}-ден бастап).",
            )
            return redirect("assessments:attempt_result", attempt_id=last.id)

    # Resume in-progress
    if last and last.status == Attempt.Status.IN_PROGRESS:
        return redirect("assessments:attempt_take", attempt_id=last.id)

    # Final exam — show intro page with warning unless ?confirm=1
    if quiz.kind == Quiz.Kind.FINAL and request.GET.get("confirm") != "1":
        prev_best = (
            Attempt.objects.filter(user=request.user, quiz=quiz, status=Attempt.Status.SUBMITTED)
            .order_by("-score_pct").first()
        )
        return render(
            request,
            "assessments/final_exam_intro.html",
            {"quiz": quiz, "prev_best": prev_best},
        )

    qids = list(quiz.questions.values_list("id", flat=True))
    if quiz.question_count_override and quiz.question_count_override < len(qids):
        qids = random.sample(qids, quiz.question_count_override)

    attempt = Attempt.objects.create(
        quiz=quiz, user=request.user, questions_snapshot=qids, answers={}
    )
    return redirect("assessments:attempt_take", attempt_id=attempt.id)


@login_required
def attempt_take(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    if attempt.status != Attempt.Status.IN_PROGRESS:
        return redirect("assessments:attempt_result", attempt_id=attempt.id)

    # Deadline check
    if attempt.deadline and timezone.now() > attempt.deadline:
        attempt.status = Attempt.Status.EXPIRED
        attempt.submitted_at = timezone.now()
        grade_attempt(attempt)
        attempt.save()
        messages.warning(request, "Уақыты бітті, әрекет автоматты түрде тапсырылды.")
        return redirect("assessments:attempt_result", attempt_id=attempt.id)

    from .models import Question
    questions = list(
        Question.objects.filter(id__in=attempt.questions_snapshot)
        .prefetch_related("choices")
    )
    # Preserve snapshot order
    qid_index = {qid: i for i, qid in enumerate(attempt.questions_snapshot)}
    questions.sort(key=lambda q: qid_index.get(q.id, 0))

    return render(
        request,
        "assessments/attempt_take.html",
        {"attempt": attempt, "questions": questions, "quiz": attempt.quiz},
    )


@login_required
@require_POST
def attempt_submit(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    if attempt.status != Attempt.Status.IN_PROGRESS:
        return redirect("assessments:attempt_result", attempt_id=attempt.id)

    from .models import Question
    answers: dict = {}
    questions = Question.objects.filter(id__in=attempt.questions_snapshot)
    for q in questions:
        key = f"q_{q.id}"
        if q.kind == "single" or q.kind == "tf":
            v = request.POST.get(key)
            if v == "true":
                answers[str(q.id)] = True
            elif v == "false":
                answers[str(q.id)] = False
            elif v and v.isdigit():
                answers[str(q.id)] = int(v)
        elif q.kind == "multiple":
            answers[str(q.id)] = [int(x) for x in request.POST.getlist(key) if x.isdigit()]
        elif q.kind == "fill" or q.kind == "short":
            answers[str(q.id)] = (request.POST.get(key) or "").strip()
        elif q.kind == "match":
            pairs = q.payload.get("pairs") or []
            ans = {}
            for p in pairs:
                left = p["left"]
                v = request.POST.get(f"{key}_{left}")
                if v:
                    ans[left] = v
            answers[str(q.id)] = ans
        elif q.kind == "order":
            order = request.POST.get(f"{key}_order", "")
            if order:
                answers[str(q.id)] = [s for s in order.split("||") if s]

    attempt.answers = answers
    attempt.status = Attempt.Status.SUBMITTED
    attempt.submitted_at = timezone.now()
    grade_attempt(attempt)
    attempt.save()

    if attempt.is_passed:
        from gamification.services import award_xp
        award_xp(request.user, "quiz_pass", 30 if attempt.quiz.kind == "module" else 100,
                 ref=f"quiz:{attempt.quiz.id}")
        if attempt.quiz.kind == "final":
            from certificates.services import issue_certificate_if_eligible
            issue_certificate_if_eligible(request.user, attempt.quiz.course)
        messages.success(request, f"Сәтті: {attempt.score_pct}%!")
    else:
        messages.info(request, f"Сіз {attempt.score_pct}% жинадыңыз. Өтуге {attempt.quiz.pass_pct}% қажет.")

    return redirect("assessments:attempt_result", attempt_id=attempt.id)


@login_required
def attempt_result(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    from .models import Question
    questions = {
        q.id: q for q in Question.objects.filter(id__in=attempt.questions_snapshot)
        .prefetch_related("choices")
    }
    ordered = [questions[qid] for qid in attempt.questions_snapshot if qid in questions]
    return render(
        request,
        "assessments/attempt_result.html",
        {"attempt": attempt, "questions": ordered},
    )
