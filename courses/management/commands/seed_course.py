"""Seeds the «Жалпы педагогика негіздері» course from Topics.md.

Topics are grouped into 10 thematic modules. Each lesson gets stub content
that methodists can later flesh out via the admin.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from assessments.models import CaseStudy, Choice, Question, Quiz
from courses.models import Course, Lesson, Module
from gamification.services import seed_default_badges


MODULE_PLAN = [
    {
        "title": "Кіріспе: педагогика — ұстаз кәсібі",
        "summary": "Педагогика ғылымы, әдіснамасы, ұстаздың кәсіптік құзыреттіліктері және Қазақстандағы білім жүйесінің тарихы.",
        "topics": [1, 2, 3, 4],
    },
    {
        "title": "Бала дамуы және жас ерекшеліктері",
        "summary": "Балалардың дамуына әсер ететін факторлар мен жас ерекшеліктерінің кезеңдері.",
        "topics": [5, 6, 7],
    },
    {
        "title": "Тәрбие теориясы",
        "summary": "Тәрбие әлеуметтік құбылыс ретінде, оның мақсаты, заңдылықтары, принциптері және өзін-өзі тәрбиелеу.",
        "topics": [9, 10, 11],
    },
    {
        "title": "Тәрбие әдістері",
        "summary": "Тәрбие әдістері туралы ұғым, жіктелуі және оларға талдау.",
        "topics": [12, 13, 14, 15],
    },
    {
        "title": "Тәрбиенің түрлері және мазмұны",
        "summary": "Ақыл-ой, адамгершілік, экологиялық, еңбек, эстетикалық және дене тәрбиесі.",
        "topics": [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
    },
    {
        "title": "Ұжым және сынып жетекшісі",
        "summary": "Балалардың қоғамдық ұйымдары, ұжымның даму кезеңдері, сынып жетекшісінің жұмысы.",
        "topics": [28, 29, 30, 31, 32],
    },
    {
        "title": "Отбасы тәрбиесі",
        "summary": "Отбасы, мектеп пен жұртшылық арасындағы ынтымақтастық.",
        "topics": [33, 34, 35],
    },
    {
        "title": "Дидактика негіздері",
        "summary": "Оқыту процесінің мәні, заңдылықтары, принциптері және білім беру мазмұны.",
        "topics": [37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48],
    },
    {
        "title": "Оқыту әдістері және технологиялары",
        "summary": "Оқыту әдістерінің жіктелуі, ИКТ, белсенді әдістер, сын тұрғысынан ойлау, оқытудың жаңа тәсілдері.",
        "topics": [49, 50, 51, 52, 53, 54, 61, 62],
    },
    {
        "title": "Сабақты жоспарлау және басқару",
        "summary": "Сабақ түрлері, құрылымы, жоспарлау, бағалау және мектеп ісін басқару.",
        "topics": [55, 56, 57, 58, 59, 60, 63, 64, 65, 66, 68, 69, 70, 71, 72, 73, 74, 75, 76],
    },
]


SAMPLE_LESSON_BLOCKS = [
    {"type": "heading", "value": "Кіріспе"},
    {"type": "paragraph", "value": "Бұл сабақта тақырыпқа қатысты негізгі ұғымдарды қарастырамыз. Сабақ соңында тестілеу болады, сондықтан негізгі терминдер мен қағидаларға назар аударыңыз."},
    {"type": "term", "value": {"name": "Педагогика", "definition": "Адамды тәрбиелеу мен оқытудың ғылымы. Бала мен ересек адамдардың дамуын зерттейді."}},
    {
        "type": "question",
        "value": {
            "text": "Педагогика ғылымының негізгі зерттеу объектісі не?",
            "choices": [
                "Тек балалардың физикалық дамуы",
                "Адамды тәрбиелеу және оқыту үрдісі",
                "Тек мектеп әкімшілігі жұмысы",
                "Психологиялық тестілер",
            ],
            "correct": 1,
            "explanation": "Педагогика — кең мағынада адамды тәрбиелеу мен оқыту туралы ғылым.",
        },
    },
    {"type": "heading", "value": "Негізгі мазмұны"},
    {"type": "paragraph", "value": "Тақырыптың теориялық негіздері мен практикалық қолданысы. Әр ұстаз бұл тақырыпты білуі тиіс, себебі күнделікті жұмыста қолданылады."},
    {"type": "callout", "value": "💡 Маңызды: бұл тақырыпты түсіну үшін алдыңғы сабақтағы материалға сүйену қажет."},
    {
        "type": "question",
        "value": {
            "text": "Қазіргі мұғалім үшін негізгі кәсіби құзыреттіліктердің бірі — қайсысы?",
            "choices": [
                "Тек өз пәнін терең білу",
                "Тек әкімшілік тапсырмаларды орындау",
                "Цифрлық технологияларды сабақта қолдана білу",
                "Сабақтан тыс жұмыстарды елемеу",
            ],
            "correct": 2,
            "explanation": "ХХІ ғасырдағы мұғалімнің құзыреттіліктер тізіміне цифрлық дағдылар кіреді.",
        },
    },
    {"type": "heading", "value": "Қорытынды"},
    {"type": "paragraph", "value": "Қысқаша түйін: негізгі ұғымдарды меңгерген соң, келесі сабаққа өтіңіз. Сұрағыңыз болса — оң жақтағы 🤖 батырманы басып, ИИ-әдіскерге қойыңыз."},
]


SAMPLE_CASES = [
    {
        "module_idx": 1,
        "title": "Бесінші сынып оқушысы сабаққа қызықпайды",
        "situation": (
            "Әсем — 5-сыныптың оқушысы. Бастауышта үлгерімі жақсы болған, бірақ орта мектепке өткен соң "
            "көп пәндерден қызығушылығы азайып, баға да түсе бастады. Ата-анасы алаңдаулы, "
            "сынып жетекшісі Әсемнің сабақта көбіне қиялдайтынын байқайды. Әсемнің өзі: "
            "«Маған бұл материал қызық емес, не үшін керек екенін түсінбеймін» дейді."
        ),
        "questions": [
            "Бұл жағдайдың ықтимал себептерін атаңыз (жас ерекшеліктері, мотивация, отбасы факторы).",
            "Сынып жетекшісі ретінде сіз қандай қадамдар жасар едіңіз?",
            "Ата-анамен қалай жұмыс істеу керек?",
        ],
        "expert_analysis": (
            "Бұл жағдайдың түп негізі — балалардың 10-12 жас аралығындағы мотивацияның "
            "трансформациясы. Бастауышта сыртқы мотивация (мұғалім мақтауы, баға) жетіп тұрса, "
            "ересек жаста ішкі мотивация қажет: «Бұл маған не үшін керек?». Шешім үш бағытта: "
            "(1) Әсемнің қызығушылықтарын анықтап, пәндерді сол қызығушылықпен байланыстыру. "
            "(2) Жобалық тапсырмалар арқылы өз бетімен таңдау еркіндігін беру. "
            "(3) Ата-анасымен бірге үй ортасында оқу-білімнің құнын күшейту."
        ),
    },
    {
        "module_idx": 3,
        "title": "Сыныптағы конфликт: жаңа оқушы",
        "situation": (
            "7-сыныпқа жаңа оқушы — Дамир — келді. Ол басқа қаладан көшіп келген. "
            "Бір айдан кейін Дамирдің сыныптас қыздарынан мазақ көріп жүргені белгілі болды. "
            "Ол сабаққа келмей қала бастады. Сынып жетекшісі бұл жайтты бағдарламалық кездесуден білді."
        ),
        "questions": [
            "Тәрбие әдістерінің қайсысы бұл жағдайға қолайлы?",
            "Сынып ұжымымен қалай жұмыс жасайсыз?",
            "Дамирмен қандай қолдау көрсетесіз?",
        ],
        "expert_analysis": (
            "Шешім тәрбиенің үш әдісін біріктіруді талап етеді: сендіру (мазақтаушылармен жеке әңгіме), "
            "ұжымдық пікір қалыптастыру (сынып сағатында эмпатия туралы талқылау), және Дамирге "
            "сыныптағы рөл беру арқылы оны ұжымға қосу. Жедел қадам — психологпен бірлесе отырып, "
            "конфликттің тереңдігін бағалау."
        ),
    },
    {
        "module_idx": 7,
        "title": "Ата-анамен қарым-қатынас: бағаны дауласу",
        "situation": (
            "Ата-ана сізге келіп, баласына «5» қойылмаған себебін агрессивті түрде сұрап жатыр. "
            "Ол: «Менің балам білмейді деп қалай айтасыз? Бұл сіздің кәсіби білімсіздігіңіз!» дейді. "
            "Сізде өзіңізді ұстауыңыз қиын болып тұр."
        ),
        "questions": [
            "Бұл жағдайда қандай педагогикалық такт пен этика қажет?",
            "Дау-дамайды қалай сындарлы әңгімеге айналдырасыз?",
            "Алдын алу үшін қандай жүйелі шараларды ұсынар едіңіз?",
        ],
        "expert_analysis": (
            "Бұл — типтік жағдай. Принциптер: (1) Эмоцияға эмоциямен жауап бермеу. (2) Бағаны "
            "критерийлермен бекіту: жұмыстың өзіне сілтеме жасау. (3) Ата-ананың мазасыздығын "
            "мойындау: «Сіз баланың үлгеріміне алаңдайтыныңызды түсінемін». Жүйелі шара — "
            "бағалау критерийлерін сыныптың басынан бастап мөлдір ету."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed the pedagogy course with 10 modules from Topics.md"

    @transaction.atomic
    def handle(self, *args, **options):
        # Read topic list — Topics.md has one title per line; line number = topic id
        topics_path = Path(settings.BASE_DIR) / "Topics.md"
        topic_map: dict[int, str] = {}
        for idx, line in enumerate(topics_path.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if line:
                topic_map[idx] = line

        course, created = Course.objects.update_or_create(
            slug="zhalpy-pedagogika",
            defaults={
                "title": "Жалпы педагогика негіздері",
                "short_description": "Болашақ ұстаздарға арналған базалық педагогика курсы — теория, дидактика, тәрбие әдістері және мектеп тәжірибесі.",
                "description": (
                    "Бұл курс педагогикалық жоғары оқу орындарының 1-2 курс студенттеріне арналған. "
                    "10 модуль ішінде педагогика ғылымының негіздері, бала дамуы, тәрбие теориясы, "
                    "дидактика, оқыту әдістері және мектеп басқару тақырыптары қамтылады. "
                    "Әр модуль соңында тест, кейс-тапсырмалар және ИИ-әдіскермен жұмыс істеу мүмкіндігі бар."
                ),
                "level": Course.Level.BEGINNER,
                "language": "kk",
                "duration_hours": 60,
                "is_published": True,
                "has_final_exam": True,
                "final_exam_pass_pct": 70,
                "tags": "педагогика,дидактика,тәрбие,мектеп,бакалавр",
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} course: {course.title}"
        ))

        # Replace modules+lessons+quizzes+cases cleanly
        course.modules.all().delete()
        course.quizzes.all().delete()
        course.cases.all().delete()

        for m_idx, m_plan in enumerate(MODULE_PLAN, start=1):
            module = Module.objects.create(
                course=course,
                title=m_plan["title"],
                summary=m_plan["summary"],
                order=m_idx,
                has_test=True,
            )
            for l_idx, topic_id in enumerate(m_plan["topics"], start=1):
                topic_title = topic_map.get(topic_id, f"Тақырып {topic_id}")
                slug = f"l{m_idx}-{l_idx}"
                Lesson.objects.create(
                    module=module,
                    title=topic_title,
                    slug=slug,
                    order=l_idx,
                    summary=f"{m_plan['title']} модулінің {l_idx}-сабағы",
                    content=SAMPLE_LESSON_BLOCKS,
                    duration_minutes=12,
                    is_free_preview=(m_idx == 1 and l_idx == 1),
                )

            # Module quiz with a few starter questions
            quiz = Quiz.objects.create(
                course=course,
                module=module,
                kind=Quiz.Kind.MODULE,
                title=f"«{m_plan['title']}» модулінің тесті",
                description="Модульді бекіту үшін тест.",
                pass_pct=70,
                cooldown_minutes=30,
            )
            for q_idx in range(1, 4):
                q = Question.objects.create(
                    quiz=quiz,
                    kind=Question.Kind.SINGLE,
                    text=f"{m_plan['title']} модуліне қатысты сұрақ {q_idx}: "
                         f"төмендегілердің қайсысы дұрыс?",
                    explanation="Дұрыс жауапты модуль материалынан таба аласыз.",
                    points=1,
                    order=q_idx,
                )
                Choice.objects.create(question=q, text="Дұрыс жауап", is_correct=True, order=1)
                Choice.objects.create(question=q, text="Жалған тұжырым A", is_correct=False, order=2)
                Choice.objects.create(question=q, text="Жалған тұжырым B", is_correct=False, order=3)
                Choice.objects.create(question=q, text="Жалған тұжырым C", is_correct=False, order=4)

        # Final exam
        final = Quiz.objects.create(
            course=course,
            module=None,
            kind=Quiz.Kind.FINAL,
            title=f"«{course.title}» — финалдық емтихан",
            description="Барлық 10 модульді қамтитын қорытынды емтихан. Уақыты 90 минут.",
            time_limit_minutes=90,
            pass_pct=70,
            cooldown_minutes=60 * 24,
            question_count_override=20,
        )
        for q_idx in range(1, 11):
            q = Question.objects.create(
                quiz=final,
                kind=Question.Kind.SINGLE,
                text=f"Финалдық сұрақ {q_idx}: педагогикаға қатысты тұжырымдардан дұрысын таңдаңыз.",
                explanation="Дұрыс жауапты курс материалынан таба аласыз.",
                points=5,
                order=q_idx,
            )
            Choice.objects.create(question=q, text=f"Дұрыс тұжырым {q_idx}", is_correct=True, order=1)
            Choice.objects.create(question=q, text="Жалған A", is_correct=False, order=2)
            Choice.objects.create(question=q, text="Жалған B", is_correct=False, order=3)
            Choice.objects.create(question=q, text="Жалған C", is_correct=False, order=4)

        # Cases
        modules = list(course.modules.order_by("order"))
        CaseStudy.objects.filter(course=course).delete()
        for cs in SAMPLE_CASES:
            module = modules[cs["module_idx"]] if cs["module_idx"] < len(modules) else None
            CaseStudy.objects.create(
                course=course,
                module=module,
                title=cs["title"],
                situation=cs["situation"],
                questions=cs["questions"],
                expert_analysis=cs["expert_analysis"],
                rubric={},
                difficulty=CaseStudy.Difficulty.MEDIUM,
                min_words=150,
                is_published=True,
            )

        n_badges = seed_default_badges()
        self.stdout.write(self.style.SUCCESS(
            f"Modules: {len(MODULE_PLAN)}, Lessons: {Lesson.objects.filter(module__course=course).count()}, "
            f"Cases: {course.cases.count()}, Badges seeded: {n_badges}"
        ))
