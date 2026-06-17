"""Pure grading functions for quiz questions."""
from typing import Any


def _norm_text(s: str) -> str:
    return (s or "").strip().lower()


def grade_single(question, answer) -> tuple[int, int, str]:
    correct_ids = question.correct_choice_ids()
    if not correct_ids:
        return 0, question.points, "Сұрақ дұрыс конфигурацияланбаған"
    picked = answer if isinstance(answer, int) else (answer[0] if isinstance(answer, list) and answer else None)
    is_ok = picked in correct_ids
    return (question.points if is_ok else 0), question.points, ""


def grade_multiple(question, answer) -> tuple[int, int, str]:
    correct = set(question.correct_choice_ids())
    picked = set(answer if isinstance(answer, list) else [])
    if not correct:
        return 0, question.points, ""
    # Partial credit: Jaccard-like; full = exact match
    if picked == correct:
        return question.points, question.points, ""
    if not picked:
        return 0, question.points, ""
    intersection = correct & picked
    wrong = picked - correct
    score = max(0, len(intersection) - len(wrong)) / len(correct)
    earned = int(round(score * question.points))
    return earned, question.points, ""


def grade_true_false(question, answer) -> tuple[int, int, str]:
    correct = question.payload.get("answer")  # True or False
    is_ok = bool(answer) == bool(correct)
    return (question.points if is_ok else 0), question.points, ""


def grade_fill(question, answer) -> tuple[int, int, str]:
    accepted = [_norm_text(a) for a in (question.payload.get("answers") or [])]
    is_ok = _norm_text(str(answer)) in accepted
    return (question.points if is_ok else 0), question.points, ""


def grade_matching(question, answer) -> tuple[int, int, str]:
    pairs = question.payload.get("pairs") or []
    correct = {p["left"]: p["right"] for p in pairs}
    picked = answer if isinstance(answer, dict) else {}
    if not correct:
        return 0, question.points, ""
    hits = sum(1 for k, v in picked.items() if correct.get(k) == v)
    earned = int(round(hits / len(correct) * question.points))
    return earned, question.points, ""


def grade_ordering(question, answer) -> tuple[int, int, str]:
    correct = question.payload.get("items") or []
    picked = answer if isinstance(answer, list) else []
    if not correct:
        return 0, question.points, ""
    if picked == correct:
        return question.points, question.points, ""
    hits = sum(1 for i, x in enumerate(picked) if i < len(correct) and x == correct[i])
    earned = int(round(hits / len(correct) * question.points))
    return earned, question.points, ""


def grade_short(question, answer, ai_result: dict | None = None) -> tuple[int, int, str]:
    """Short open answers — AI-graded.

    If ai_result is provided it should be {"verdict": "correct"|"partial"|"wrong", "feedback": "..."}.
    Falls back to exact reference match if AI not available.
    """
    if ai_result:
        verdict = ai_result.get("verdict")
        feedback = ai_result.get("feedback", "")
        if verdict == "correct":
            return question.points, question.points, feedback
        if verdict == "partial":
            return max(1, question.points // 2), question.points, feedback
        return 0, question.points, feedback
    ref = _norm_text(question.payload.get("reference", ""))
    if ref and _norm_text(str(answer)) == ref:
        return question.points, question.points, ""
    return 0, question.points, "ИИ бағалауы қолжетімсіз"


GRADERS = {
    "single": grade_single,
    "multiple": grade_multiple,
    "tf": grade_true_false,
    "fill": grade_fill,
    "match": grade_matching,
    "order": grade_ordering,
    "short": grade_short,
}


def grade_attempt(attempt) -> dict[str, Any]:
    """Mutates attempt.results, attempt.points_*, attempt.score_pct."""
    from .models import Question
    qids = attempt.questions_snapshot or list(attempt.quiz.questions.values_list("id", flat=True))
    questions = {q.id: q for q in Question.objects.filter(id__in=qids).prefetch_related("choices")}
    results: dict[str, Any] = {}
    earned = 0
    total = 0
    for qid in qids:
        q = questions.get(qid)
        if not q:
            continue
        answer = attempt.answers.get(str(qid)) if isinstance(attempt.answers, dict) else None
        grader = GRADERS.get(q.kind, grade_single)
        if q.kind == "short":
            pts, mx, fb = grader(q, answer, None)
        else:
            pts, mx, fb = grader(q, answer)
        results[str(qid)] = {
            "points": pts,
            "max": mx,
            "feedback": fb,
            "correct": pts == mx,
        }
        earned += pts
        total += mx
    attempt.points_earned = earned
    attempt.points_max = total
    attempt.score_pct = int(round(earned * 100 / total)) if total else 0
    attempt.results = results
    return results
