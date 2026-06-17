"""Generate rich lesson content for each lesson via OpenAI.

Usage:
  python manage.py generate_lessons --course zhalpy-pedagogika --modules 1 2 3
  python manage.py generate_lessons --course zhalpy-pedagogika --all
  python manage.py generate_lessons --course zhalpy-pedagogika --limit 5
"""
import json
import time
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from aitutor.models import AICallLog
from courses.models import Course, Lesson


SYSTEM_PROMPT = """Сен — болашақ ұстаздарға арналған казақ тіліндегі педагогика курсының контент-авторысың.
Студент 18-25 жастағы педагогикалық университеттің студенті.

Сабақ үшін құрылымдалған, нақты және қызықты контент жаз. Тек қазақ тілінде.
Жалпы сөздер мен судан гөрі — нақты мысалдар, терминдер, педагогикалық тұжырымдар."""


USER_PROMPT_TEMPLATE = """САБАҚ: «{lesson_title}»
МОДУЛЬ: «{module_title}»
КУРС: «{course_title}»

Осы тақырып бойынша сабақ контентін JSON форматта жаса. Құрылым:

{{
  "blocks": [
    {{"type": "paragraph", "value": "Кіріспе абзац — неліктен бұл тақырып маңызды, болашақ мұғалімге қалай керек (2-4 сөйлем)"}},

    {{"type": "term", "value": {{"name": "Негізгі термин", "definition": "Тақырыпқа қатысты маңызды ұғымның анықтамасы (1-2 сөйлем)"}}}},

    {{"type": "heading", "value": "Негізгі мазмұны"}},
    {{"type": "paragraph", "value": "Тақырыпты ашатын негізгі абзац: түсініктер, тұжырымдар, ерекшеліктер (3-5 сөйлем)"}},
    {{"type": "paragraph", "value": "Тағы бір абзац: тереңірек қарастыру, әртүрлі көзқарастар (3-5 сөйлем)"}},

    {{"type": "callout", "value": "💡 Практикалық кеңес немесе мысал — нақты сыныптағы жағдай арқылы"}},

    {{"type": "question", "value": {{
      "text": "Тақырып бойынша 1-сұрақ (нақты, нақты педагогикалық жағдайды тексеретін)",
      "choices": ["А нұсқа", "Б нұсқа", "В нұсқа", "Г нұсқа"],
      "correct": 0,
      "explanation": "Дұрыс жауаптың түсіндірмесі (1-2 сөйлем)"
    }}}},

    {{"type": "heading", "value": "Практикалық қолданысы"}},
    {{"type": "paragraph", "value": "Тақырыпты сабақта қалай қолдану туралы абзац (3-5 сөйлем)"}},

    {{"type": "list", "value": ["Нақты қадам 1", "Нақты қадам 2", "Нақты қадам 3"]}},

    {{"type": "question", "value": {{
      "text": "Тақырып бойынша 2-сұрақ (бірінші сұрақтан өзгеше аспектіні тексеретін)",
      "choices": ["А нұсқа", "Б нұсқа", "В нұсқа", "Г нұсқа"],
      "correct": 2,
      "explanation": "Дұрыс жауаптың түсіндірмесі"
    }}}},

    {{"type": "paragraph", "value": "Қорытынды абзац — негізгі ойды бекіту, келесі сабаққа көпір (2-3 сөйлем)"}}
  ]
}}

Тек JSON қайтар. Қазақ тілі дұрыс болсын. Сұрақтар нақты тақырыппен байланысты болсын. "correct" индексі 0-3 аралығында болсын (қай нұсқа дұрыс)."""


class Command(BaseCommand):
    help = "Generate per-lesson content via OpenAI"

    def add_arguments(self, parser):
        parser.add_argument("--course", default="zhalpy-pedagogika", help="Course slug")
        parser.add_argument("--modules", nargs="+", type=int, default=None,
                            help="Module orders to process (e.g. --modules 1 2 3)")
        parser.add_argument("--all", action="store_true", help="Process all modules")
        parser.add_argument("--limit", type=int, default=None, help="Stop after N lessons")
        parser.add_argument("--force", action="store_true",
                            help="Overwrite lessons that already have non-default content")
        parser.add_argument("--dry-run", action="store_true", help="Print plan only")

    def handle(self, *args, **opts):
        if not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is not set in .env")

        try:
            course = Course.objects.get(slug=opts["course"])
        except Course.DoesNotExist:
            raise CommandError(f"Course '{opts['course']}' not found")

        # Pick lessons
        lessons_q = Lesson.objects.filter(module__course=course).select_related("module")
        if opts["modules"]:
            lessons_q = lessons_q.filter(module__order__in=opts["modules"])
        elif not opts["all"]:
            raise CommandError("Pass --modules 1 2 3  OR  --all")
        lessons_q = lessons_q.order_by("module__order", "order")

        lessons = list(lessons_q)
        if opts["limit"]:
            lessons = lessons[: opts["limit"]]

        self.stdout.write(self.style.NOTICE(
            f"About to generate content for {len(lessons)} lesson(s) in course «{course.title}»"
        ))
        if opts["dry_run"]:
            for ln in lessons:
                self.stdout.write(f"  · M{ln.module.order}.{ln.order} {ln.title}")
            return

        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        model = settings.OPENAI_MODEL_CHEAP
        total_cost = Decimal("0")
        ok_count = 0
        skip_count = 0
        fail_count = 0

        for i, ln in enumerate(lessons, 1):
            # Skip if already has substantial content (more than default template)
            existing = ln.content or []
            has_real_content = any(
                isinstance(b, dict) and b.get("type") == "paragraph"
                and len(str(b.get("value", ""))) > 150
                for b in existing
            )
            if has_real_content and not opts["force"]:
                self.stdout.write(f"  [{i}/{len(lessons)}] SKIP (already has content): {ln.title[:50]}")
                skip_count += 1
                continue

            self.stdout.write(f"  [{i}/{len(lessons)}] gen: M{ln.module.order}.{ln.order} {ln.title[:60]}", ending="")
            self.stdout.flush()
            t0 = time.monotonic()
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                            lesson_title=ln.title,
                            module_title=ln.module.title,
                            course_title=course.title,
                        )},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                    max_tokens=2200,
                )
                raw = resp.choices[0].message.content or "{}"
                data = json.loads(raw)
                blocks = data.get("blocks", [])

                if not blocks or not isinstance(blocks, list):
                    self.stdout.write(self.style.ERROR(f"  ← bad shape, skipping"))
                    fail_count += 1
                    continue

                # Validate question blocks
                for b in blocks:
                    if isinstance(b, dict) and b.get("type") == "question":
                        v = b.get("value", {})
                        if not isinstance(v.get("choices"), list) or len(v["choices"]) < 2:
                            b["type"] = "paragraph"
                            b["value"] = v.get("text", "")
                        else:
                            v["correct"] = max(0, min(len(v["choices"]) - 1, int(v.get("correct", 0))))

                ln.content = blocks
                ln.save(update_fields=["content", "updated_at"])

                # Log AI cost
                from decimal import Decimal as D
                pt = resp.usage.prompt_tokens
                ct = resp.usage.completion_tokens
                cost = D(pt) / 1000 * D("0.00015") + D(ct) / 1000 * D("0.0006")
                total_cost += cost
                AICallLog.objects.create(
                    user=None, purpose="practice", model=model,
                    prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct,
                    cost_usd=cost, latency_ms=int((time.monotonic() - t0) * 1000),
                    success=True, ref=f"gen-lesson:{ln.id}",
                )
                ok_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ← {len(blocks)} blocks, ${cost:.4f}, {(time.monotonic()-t0):.1f}s"
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ← FAIL: {e}"))
                fail_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"DONE. generated={ok_count}  skipped={skip_count}  failed={fail_count}  cost=${total_cost:.4f}"
        ))
