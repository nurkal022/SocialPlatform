from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from assessments.models import CaseSubmission
from courses.models import Course, Lesson

from .models import Comment, CommentLike, CourseReview, Report


@login_required
@require_POST
def add_comment(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    body = (request.POST.get("body") or "").strip()
    parent_id = request.POST.get("parent_id")
    if not body:
        return redirect(lesson.get_absolute_url())
    parent = Comment.objects.filter(pk=parent_id, lesson=lesson).first() if parent_id else None
    Comment.objects.create(lesson=lesson, user=request.user, parent=parent, body=body)
    return redirect(lesson.get_absolute_url() + "#comments")


@login_required
@require_POST
def like_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    existing = CommentLike.objects.filter(comment=comment, user=request.user).first()
    if existing:
        existing.delete()
        liked = False
    else:
        CommentLike.objects.create(comment=comment, user=request.user)
        liked = True
    return JsonResponse({"liked": liked, "count": comment.likes.count()})


@login_required
@require_POST
def add_review(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    try:
        rating = max(1, min(5, int(request.POST.get("rating", "5"))))
    except ValueError:
        rating = 5
    body = (request.POST.get("body") or "").strip()
    CourseReview.objects.update_or_create(
        course=course, user=request.user,
        defaults={"rating": rating, "body": body},
    )
    messages.success(request, "Шолуыңыз сақталды. Рақмет!")
    return redirect("courses:detail", slug=course.slug)


@login_required
@require_POST
def report(request, kind, target_id):
    reason = (request.POST.get("reason") or "").strip()
    if reason:
        Report.objects.create(
            reporter=request.user, kind=kind, target_id=target_id, reason=reason
        )
        messages.info(request, "Шағым жіберілді, модератор қарайды.")
    return redirect(request.META.get("HTTP_REFERER", "/"))


def best_solutions(request):
    qs = (
        CaseSubmission.objects.filter(is_public=True, status=CaseSubmission.Status.GRADED)
        .select_related("user", "case")
        .order_by("-score", "-submitted_at")[:50]
    )
    from django.shortcuts import render
    return render(request, "social/best_solutions.html", {"submissions": qs})
