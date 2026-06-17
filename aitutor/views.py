import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from courses.models import Lesson

from .models import TutorMessage
from .services import (
    AIRateLimited,
    AIServiceUnavailable,
    generate_practice_questions,
    stream_tutor_reply,
)


@login_required
def tutor_panel(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    history = TutorMessage.objects.filter(
        user=request.user, lesson=lesson
    ).order_by("created_at")[:50]
    return render(
        request,
        "aitutor/panel.html",
        {"lesson": lesson, "history": history},
    )


@login_required
@require_POST
@csrf_protect
def tutor_send(request, lesson_id):
    """Streams reply via SSE-like chunked transfer."""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        data = {}
    user_text = (data.get("message") or "").strip()
    if not user_text:
        return JsonResponse({"error": "Бос хабарлама"}, status=400)

    # Build chat history (last 12 turns)
    hist = list(
        TutorMessage.objects.filter(user=request.user, lesson=lesson)
        .exclude(role=TutorMessage.Role.SYSTEM)
        .order_by("-created_at")[:12]
    )
    hist.reverse()
    messages = [{"role": m.role, "content": m.content} for m in hist]
    messages.append({"role": "user", "content": user_text})

    def gen():
        try:
            for chunk in stream_tutor_reply(user=request.user, lesson=lesson, messages=messages):
                yield chunk
        except AIRateLimited as e:
            yield f"\n\n[Күндік ИИ лимиті: {e}]"
        except AIServiceUnavailable as e:
            yield f"\n\n[ИИ қолжетімсіз: {e}]"

    resp = StreamingHttpResponse(gen(), content_type="text/plain; charset=utf-8")
    resp["X-Accel-Buffering"] = "no"
    resp["Cache-Control"] = "no-cache"
    return resp


@login_required
@require_POST
def rate_message(request, message_id):
    msg = get_object_or_404(TutorMessage, pk=message_id, user=request.user)
    try:
        rating = int(request.POST.get("rating", "0"))
    except ValueError:
        rating = 0
    msg.rating = max(-1, min(1, rating))
    msg.save(update_fields=["rating"])
    return JsonResponse({"ok": True})


@login_required
def practice(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    questions: list = []
    error = ""
    if request.method == "POST":
        try:
            questions = generate_practice_questions(lesson, user=request.user, n=5)
        except (AIServiceUnavailable, AIRateLimited) as e:
            error = str(e)
    return render(
        request,
        "aitutor/practice.html",
        {"lesson": lesson, "questions": questions, "error": error},
    )
