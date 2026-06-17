"""Thin OpenAI wrapper.

Isolated so swapping providers is a one-file change.
"""
from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("aitutor")


class AIServiceUnavailable(Exception):
    """OpenAI not configured or call failed."""


class AIRateLimited(Exception):
    """Per-user daily quota exhausted."""


# rough pricing per 1k tokens, USD — update as needed
PRICING = {
    "gpt-4o-mini": (Decimal("0.00015"), Decimal("0.0006")),
    "gpt-4o": (Decimal("0.0025"), Decimal("0.01")),
}


def _client():
    if not settings.OPENAI_API_KEY:
        raise AIServiceUnavailable("OPENAI_API_KEY is not set")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise AIServiceUnavailable(f"openai package not installed: {e}")
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _check_quota(user, purpose: str):
    from .models import AICallLog
    if not user or not user.is_authenticated:
        return
    if purpose == AICallLog.Purpose.TUTOR:
        limit = settings.AI_TUTOR_DAILY_LIMIT
    elif purpose == AICallLog.Purpose.CASE:
        limit = settings.AI_CASE_GRADE_DAILY_LIMIT
    else:
        return
    used = AICallLog.objects.filter(
        user=user, purpose=purpose, created_at__date=timezone.now().date(), success=True
    ).count()
    if used >= limit:
        raise AIRateLimited(f"Күндік лимит: {limit}, бүгін: {used}")


def _log_call(user, purpose, model, usage, latency_ms, success=True, error="", ref=""):
    from .models import AICallLog
    pt = getattr(usage, "prompt_tokens", 0) if usage else 0
    ct = getattr(usage, "completion_tokens", 0) if usage else 0
    tt = getattr(usage, "total_tokens", pt + ct) if usage else 0
    p_in, p_out = PRICING.get(model, (Decimal("0"), Decimal("0")))
    cost = (Decimal(pt) / 1000) * p_in + (Decimal(ct) / 1000) * p_out
    AICallLog.objects.create(
        user=user if (user and user.is_authenticated) else None,
        purpose=purpose,
        model=model,
        prompt_tokens=pt,
        completion_tokens=ct,
        total_tokens=tt,
        cost_usd=cost,
        latency_ms=latency_ms,
        success=success,
        error=error,
        ref=ref,
    )


TUTOR_SYSTEM = """Сен — болашақ ұстаздарға арналған «Ұстаз» академиясының педагогика пәнінен әдіскер-көмекшісің.
Қазақ тілінде, нақты, қысқа және сабырлы стильде жауап бер.
Тек педагогика, психология, әдістеме, мектеп тәжірибесіне қатысты сұрақтарға жауап бер.
Басқа тақырыпқа қатысты сұрақ түссе, сыпайы түрде педагогикаға бағыттай отырып, көмектесуден бас тарт.
Қажет болғанда сабақтың мәтінінен мысал келтір, бірақ оқушыға тапсырманы өзі үшін шешіп берме — оны ойлануға бағытта."""


def stream_tutor_reply(
    *,
    user,
    lesson,
    messages: list[dict],
) -> Iterable[str]:
    """Yields text chunks. Saves user msg & assistant reply to DB at the end."""
    from .models import AICallLog, TutorMessage
    _check_quota(user, AICallLog.Purpose.TUTOR)

    lesson_ctx = ""
    if lesson:
        lesson_ctx = (
            f"\n\n=== Ағымдағы сабақ: «{lesson.title}» (модуль: «{lesson.module.title}») ===\n"
            f"{lesson.plain_text()[:6000]}"
        )

    full_messages = [
        {"role": "system", "content": TUTOR_SYSTEM + lesson_ctx},
        *messages,
    ]

    # Save the latest user message
    if messages and messages[-1]["role"] == "user":
        TutorMessage.objects.create(
            user=user, lesson=lesson, role=TutorMessage.Role.USER,
            content=messages[-1]["content"],
        )

    client = _client()
    model = settings.OPENAI_MODEL_CHEAP
    started = time.monotonic()
    collected: list[str] = []
    usage = None
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=full_messages,
            stream=True,
            temperature=0.4,
            max_tokens=800,
            stream_options={"include_usage": True},
        )
        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    collected.append(delta.content)
                    yield delta.content
            if getattr(chunk, "usage", None):
                usage = chunk.usage
    except Exception as e:
        logger.exception("tutor stream failed")
        _log_call(
            user, AICallLog.Purpose.TUTOR, model, None,
            int((time.monotonic() - started) * 1000),
            success=False, error=str(e), ref=f"lesson:{lesson.id}" if lesson else "",
        )
        raise AIServiceUnavailable(str(e))

    latency = int((time.monotonic() - started) * 1000)
    reply = "".join(collected)
    TutorMessage.objects.create(
        user=user, lesson=lesson, role=TutorMessage.Role.ASSISTANT, content=reply,
    )
    _log_call(
        user, AICallLog.Purpose.TUTOR, model, usage, latency,
        ref=f"lesson:{lesson.id}" if lesson else "",
    )


CASE_GRADE_INSTRUCTIONS = """Сен — педагогика пәні бойынша тәжірибелі әдіскерсің.
Студенттің кейс-ситуацияға берген жауабын келесі критерийлер бойынша 0-100 ұпай шкаласымен баға.

Жауабыңды ҚАТАҢ түрде келесі JSON форматта қайтар:
{{
  "score": <0-100 жалпы ұпай>,
  "criteria": [
    {{"name": "...", "weight": <0-100>, "score": <0-100>, "comment": "..."}},
    ...
  ],
  "strengths": ["..."],
  "improvements": ["..."],
  "feedback": "2-4 сөйлемдік жалпы кері байланыс қазақ тілінде"
}}

JSON-нан басқа ештеңе жазба. Барлық мәтін қазақ тілінде."""


def grade_case_submission(case, response_text: str, *, user) -> dict:
    from .models import AICallLog
    _check_quota(user, AICallLog.Purpose.CASE)
    rubric = case.default_rubric()
    rubric_lines = "\n".join(
        f"- {c['name']} (салмағы {c.get('weight', 0)}%): {c.get('description', '')}"
        for c in rubric.get("criteria", [])
    )
    user_prompt = f"""КЕЙС: {case.title}

ЖАҒДАЙ:
{case.situation}

СҰРАҚТАР:
{chr(10).join('- ' + q for q in (case.questions or []))}

КРИТЕРИЙЛЕР:
{rubric_lines}

СТУДЕНТТІҢ ЖАУАБЫ:
\"\"\"{response_text}\"\"\""""

    client = _client()
    model = settings.OPENAI_MODEL_SMART
    started = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CASE_GRADE_INSTRUCTIONS},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1500,
        )
    except Exception as e:
        logger.exception("case grade failed")
        _log_call(
            user, AICallLog.Purpose.CASE, model, None,
            int((time.monotonic() - started) * 1000),
            success=False, error=str(e), ref=f"case:{case.id}",
        )
        raise AIServiceUnavailable(str(e))

    latency = int((time.monotonic() - started) * 1000)
    raw = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"score": 0, "feedback": raw, "criteria": []}
    _log_call(user, AICallLog.Purpose.CASE, model, resp.usage, latency, ref=f"case:{case.id}")
    return data


def grade_short_answer(question, answer_text: str, *, user) -> dict:
    """Returns {"verdict": "correct"|"partial"|"wrong", "feedback": "..."}"""
    from .models import AICallLog
    client = _client()
    model = settings.OPENAI_MODEL_CHEAP
    reference = question.payload.get("reference", "")
    prompt = f"""Сұрақ: {question.text}
Эталондық жауап: {reference}
Студент жауабы: \"\"\"{answer_text}\"\"\"

JSON форматта қайтар:
{{"verdict": "correct"|"partial"|"wrong", "feedback": "1 сөйлем қазақ тілінде"}}"""
    started = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Сен педагогика әдіскерісің. Қысқа жауаптарды бағала."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200,
        )
    except Exception as e:
        _log_call(
            user, AICallLog.Purpose.SHORT, model, None,
            int((time.monotonic() - started) * 1000),
            success=False, error=str(e), ref=f"q:{question.id}",
        )
        raise AIServiceUnavailable(str(e))
    latency = int((time.monotonic() - started) * 1000)
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        data = {"verdict": "wrong", "feedback": ""}
    _log_call(user, AICallLog.Purpose.SHORT, model, resp.usage, latency, ref=f"q:{question.id}")
    return data


def generate_practice_questions(lesson, *, user, n: int = 5) -> list[dict]:
    client = _client()
    model = settings.OPENAI_MODEL_CHEAP
    prompt = f"""Сабақ: {lesson.title}
Мәтін:
{lesson.plain_text()[:6000]}

Осы сабақ бойынша {n} жаттығу сұрағы жаса.
JSON форматта қайтар:
{{"questions": [
  {{"question": "...", "answer": "...", "hint": "..."}},
  ...
]}}"""
    started = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Педагогика бойынша тренировкалық сұрақтар құрастырушысың."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=1200,
        )
    except Exception as e:
        from .models import AICallLog
        _log_call(
            user, AICallLog.Purpose.PRACTICE, model, None,
            int((time.monotonic() - started) * 1000),
            success=False, error=str(e), ref=f"lesson:{lesson.id}",
        )
        raise AIServiceUnavailable(str(e))
    latency = int((time.monotonic() - started) * 1000)
    from .models import AICallLog
    _log_call(user, AICallLog.Purpose.PRACTICE, model, resp.usage, latency, ref=f"lesson:{lesson.id}")
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
        return data.get("questions", [])
    except json.JSONDecodeError:
        return []
