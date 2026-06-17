"""Seed realistic comments + reviews from test users so the site feels populated.

Usage:
  python manage.py seed_social
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import Course, Lesson
from social.models import Comment, CommentLike, CourseReview


COMMENT_TEMPLATES = [
    "Бұл сабақ өте пайдалы болды, рахмет!",
    "Тақырып қызықты ұсынылған. Әсіресе соңғы абзац ұнады.",
    "Сұрағым бар: бұл идеяны бастауыш сыныпта да қолдануға бола ма?",
    "Чекпоинт сұрақтары шынымен ойландырады. Жақсы тәсіл!",
    "Менің ойымша, тарихи мысалдар жетіспейді. Қосуға болар ма?",
    "Бұл материалды практикада көп қолдандым, өте дұрыс құрастырылған.",
    "Әдіскерге үлкен рахмет — нақты, түсінікті.",
    "Маған ИИ-көмекші өте ұнады. Сұраққа жауап жылдам.",
    "Терминдер жақсы анықталған, осындай нақтылықты іздеп жүр едім.",
    "Сабақ қысқа, бірақ мазмұнды. Уақыты тиімді бөлінген.",
    "Бұл тақырыпта Макаренконың еңбектерін оқуды ұсынар едім.",
    "Менің мектептегі тәжірибемнен мысал: ...",
    "Видео көрсетілім сабақтың сапасын арттырды.",
    "Алдын ала білмеген ақпарат — кәсіби деңгейім өсті.",
    "Тестті 90% ұпайға тапсырдым, ұнады!",
]

REPLY_TEMPLATES = [
    "Әбден келісемін, өзім де солай ойлаймын.",
    "Жақсы тұжырым! Қосарым: ...",
    "Маған да осы сұрақ ұнады, нақтырақ қарастыруға болар еді.",
    "Тәжірибеңізбен бөліскеніңіз үшін рахмет.",
    "Иә, мен де осыны байқадым.",
]

REVIEW_TEMPLATES_GOOD = [
    ("Курс өте мазмұнды әрі жақсы құрылымдалған. Болашақ ұстаздарға міндетті деп санаймын.", 5),
    ("Әр модуль сапалы дайындалған. Кейстер шынайы, тестер де қиын. Рахмет!", 5),
    ("ИИ-әдіскер өте көмектесті. Курс уақытты тиімді өткізді.", 5),
    ("Жалпы алғанда жақсы курс. Кейбір модульдер тым қысқа сияқты, бірақ негізгі ойды берген.", 4),
    ("Мазмұн күшті, бірақ кейбір жерлерде көбірек тәжірибелік мысал қажет.", 4),
    ("Жаңа бастаушыға өте қолайлы. Жан-жақты педагогика негіздерін қамтиды.", 5),
    ("Қазақ тіліндегі осындай платформаны көптен күткен едім. Үлкен рахмет!", 5),
    ("Тестілеу жүйесі ыңғайлы, кейстер шынайы. Тек видеоны көбейтсе деген.", 4),
]


class Command(BaseCommand):
    help = "Seed realistic social activity (comments + reviews)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Wipe existing comments + reviews first")

    def handle(self, *args, **opts):
        U = get_user_model()
        # Pool of authors — anyone enrolled
        users = list(U.objects.filter(enrollments__isnull=False).distinct())
        if len(users) < 2:
            self.stdout.write(self.style.WARNING(
                "Need ≥2 enrolled users. Run seed_test_accounts first."
            ))
            return

        if opts["reset"]:
            n_c = Comment.objects.count()
            n_r = CourseReview.objects.count()
            Comment.objects.all().delete()
            CourseReview.objects.all().delete()
            self.stdout.write(f"  removed {n_c} comments + {n_r} reviews")

        rng = random.Random(42)

        # Seed comments on ~30 lessons across both courses
        lessons = list(Lesson.objects.select_related("module__course").all())
        rng.shuffle(lessons)
        target_lessons = lessons[:30]
        comment_count = 0
        reply_count = 0
        like_count = 0
        for lesson in target_lessons:
            n_top = rng.randint(1, 4)
            for _ in range(n_top):
                author = rng.choice(users)
                created = timezone.now() - timedelta(
                    days=rng.randint(1, 20), hours=rng.randint(0, 23)
                )
                c = Comment.objects.create(
                    lesson=lesson, user=author,
                    body=rng.choice(COMMENT_TEMPLATES),
                )
                Comment.objects.filter(pk=c.pk).update(created_at=created)
                comment_count += 1
                # 50% — get 1-2 replies
                if rng.random() < 0.5:
                    for _ in range(rng.randint(1, 2)):
                        replier = rng.choice([u for u in users if u != author])
                        rc = Comment.objects.create(
                            lesson=lesson, user=replier, parent=c,
                            body=rng.choice(REPLY_TEMPLATES),
                        )
                        Comment.objects.filter(pk=rc.pk).update(
                            created_at=created + timedelta(hours=rng.randint(1, 48))
                        )
                        reply_count += 1
                # Random likes
                liker_count = rng.randint(0, min(len(users) - 1, 4))
                for liker in rng.sample([u for u in users if u != author], liker_count):
                    CommentLike.objects.get_or_create(comment=c, user=liker)
                    like_count += 1

        # Seed reviews on both courses
        review_count = 0
        for course in Course.objects.filter(is_published=True):
            for user in users:
                if rng.random() > 0.7:
                    continue  # not everyone reviews
                body, rating = rng.choice(REVIEW_TEMPLATES_GOOD)
                created = timezone.now() - timedelta(days=rng.randint(2, 30))
                r, _ = CourseReview.objects.update_or_create(
                    course=course, user=user,
                    defaults={"rating": rating, "body": body},
                )
                CourseReview.objects.filter(pk=r.pk).update(created_at=created)
                review_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"DONE. comments={comment_count}, replies={reply_count}, "
            f"likes={like_count}, reviews={review_count}"
        ))
