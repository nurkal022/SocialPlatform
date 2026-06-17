from django.conf import settings
from django.db import models
from django.utils import timezone

from courses.models import Course, Module


class Quiz(models.Model):
    class Kind(models.TextChoices):
        MODULE = "module", "Модуль тесті"
        FINAL = "final", "Финалдық емтихан"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="quizzes")
    module = models.OneToOneField(
        Module, on_delete=models.CASCADE, null=True, blank=True, related_name="quiz"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.MODULE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(default=0, help_text="0 = шектеусіз")
    pass_pct = models.PositiveSmallIntegerField(default=70)
    cooldown_minutes = models.PositiveIntegerField(default=30)
    question_count_override = models.PositiveIntegerField(
        default=0, help_text="0 = барлық сұрақтар; әйтпесе кездейсоқ N таңдалады"
    )
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["course", "kind"]
        verbose_name_plural = "Quizzes"

    def __str__(self):
        return self.title


class Question(models.Model):
    class Kind(models.TextChoices):
        SINGLE = "single", "Бір дұрыс жауап"
        MULTIPLE = "multiple", "Бірнеше дұрыс жауап"
        TRUE_FALSE = "tf", "Дұрыс / Бұрыс"
        FILL_BLANK = "fill", "Бос орынды толтыр"
        MATCHING = "match", "Сәйкестендіру"
        ORDERING = "order", "Реттеу"
        SHORT = "short", "Қысқа ашық жауап"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.SINGLE)
    text = models.TextField()
    explanation = models.TextField(blank=True, help_text="Жауаптан кейін көрсетіледі")
    points = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField(default=dict, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Q{self.id}: {self.text[:60]}"

    def correct_choice_ids(self):
        return list(self.choices.filter(is_correct=True).values_list("id", flat=True))


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "Жүруде"
        SUBMITTED = "submitted", "Тапсырылды"
        EXPIRED = "expired", "Уақыты бітті"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IN_PROGRESS)
    score_pct = models.PositiveSmallIntegerField(default=0)
    points_earned = models.PositiveIntegerField(default=0)
    points_max = models.PositiveIntegerField(default=0)
    questions_snapshot = models.JSONField(default=list, blank=True)
    answers = models.JSONField(default=dict, blank=True)
    results = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user} → {self.quiz} ({self.status})"

    @property
    def is_passed(self):
        return self.status == self.Status.SUBMITTED and self.score_pct >= self.quiz.pass_pct

    @property
    def deadline(self):
        if not self.quiz.time_limit_minutes:
            return None
        return self.started_at + timezone.timedelta(minutes=self.quiz.time_limit_minutes)


class CaseStudy(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Жеңіл"
        MEDIUM = "medium", "Орта"
        HARD = "hard", "Күрделі"

    module = models.ForeignKey(
        Module, on_delete=models.SET_NULL, null=True, blank=True, related_name="cases"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="cases"
    )
    title = models.CharField(max_length=255)
    situation = models.TextField(help_text="Педагогикалық жағдайдың сипаттамасы")
    questions = models.JSONField(
        default=list, help_text="['Бұл жағдайда мұғалім не істеуі керек?', ...]"
    )
    expert_analysis = models.TextField(blank=True, help_text="Методист дайындаған эталондық талдау")
    rubric = models.JSONField(default=dict, blank=True)
    difficulty = models.CharField(max_length=8, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    min_words = models.PositiveIntegerField(default=150)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Case studies"

    def __str__(self):
        return self.title

    def default_rubric(self):
        if self.rubric and self.rubric.get("criteria"):
            return self.rubric
        return {
            "criteria": [
                {"name": "Жағдайды талдау тереңдігі", "weight": 30, "description": "Себептер мен факторларды анықтау"},
                {"name": "Шешімнің педагогикалық негіздемесі", "weight": 35, "description": "Теориялық қолдау"},
                {"name": "Практикалық қолданылуы", "weight": 25, "description": "Нақты қадамдар"},
                {"name": "Тіл сауаттылығы", "weight": 10, "description": "Терминологияның дұрыстығы"},
            ]
        }


class CaseSubmission(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Жоба"
        GRADED = "graded", "Бағаланды"
        FAILED = "failed", "Қате"

    case = models.ForeignKey(CaseStudy, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="case_submissions"
    )
    response = models.TextField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    score = models.PositiveSmallIntegerField(default=0)
    criteria_scores = models.JSONField(default=list, blank=True)
    feedback = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.user} → {self.case} ({self.score})"

    @property
    def word_count(self):
        return len((self.response or "").split())
