from django.contrib.auth import get_user_model
from django.test import TestCase

from courses.models import Course, Module
from gamification.models import Profile

from .grading import grade_attempt
from .models import Attempt, Choice, Question, Quiz

User = get_user_model()


class GradingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="grader", password="x", email="g@x.kz")
        self.course = Course.objects.create(title="T", slug="t", short_description="x", description="x", is_published=True)
        self.module = Module.objects.create(course=self.course, title="M1", order=1)
        self.quiz = Quiz.objects.create(course=self.course, module=self.module, title="Q", pass_pct=50)

    def _add_single(self, correct_idx: int):
        q = Question.objects.create(quiz=self.quiz, kind="single", text="?", points=2, order=1)
        for i in range(3):
            Choice.objects.create(question=q, text=f"c{i}", is_correct=(i == correct_idx), order=i)
        return q

    def test_single_correct(self):
        q = self._add_single(1)
        correct_choice = q.choices.get(is_correct=True)
        a = Attempt.objects.create(
            quiz=self.quiz, user=self.user, questions_snapshot=[q.id],
            answers={str(q.id): correct_choice.id},
        )
        grade_attempt(a)
        self.assertEqual(a.points_earned, 2)
        self.assertEqual(a.score_pct, 100)

    def test_single_wrong(self):
        q = self._add_single(0)
        wrong = q.choices.filter(is_correct=False).first()
        a = Attempt.objects.create(
            quiz=self.quiz, user=self.user, questions_snapshot=[q.id],
            answers={str(q.id): wrong.id},
        )
        grade_attempt(a)
        self.assertEqual(a.score_pct, 0)

    def test_multiple_partial(self):
        q = Question.objects.create(quiz=self.quiz, kind="multiple", text="?", points=4, order=1)
        c1 = Choice.objects.create(question=q, text="a", is_correct=True, order=1)
        c2 = Choice.objects.create(question=q, text="b", is_correct=True, order=2)
        Choice.objects.create(question=q, text="c", is_correct=False, order=3)
        a = Attempt.objects.create(
            quiz=self.quiz, user=self.user, questions_snapshot=[q.id],
            answers={str(q.id): [c1.id]},  # only one of two correct
        )
        grade_attempt(a)
        self.assertGreater(a.points_earned, 0)
        self.assertLess(a.points_earned, 4)


class GamificationTests(TestCase):
    def test_xp_grants_level(self):
        from gamification.services import award_xp
        u = User.objects.create_user(username="xpuser", password="x", email="x@x.kz")
        award_xp(u, "test", 600)
        p = Profile.objects.get(user=u)
        self.assertEqual(p.xp, 600)
        self.assertGreater(p.level, 1)

    def test_streak_increments(self):
        from gamification.services import _touch_streak, ensure_streak
        u = User.objects.create_user(username="streak", password="x", email="s@x.kz")
        s = ensure_streak(u)
        self.assertEqual(s.current, 0)
        _touch_streak(u)
        self.assertEqual(s.__class__.objects.get(user=u).current, 1)


class CertificateEligibilityTests(TestCase):
    def test_not_eligible_without_enrollment(self):
        from certificates.services import is_eligible
        u = User.objects.create_user(username="ce", password="x", email="ce@x.kz")
        c = Course.objects.create(title="C", slug="c", short_description="x", description="x", is_published=True)
        ok, _ = is_eligible(u, c)
        self.assertFalse(ok)
