from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Course(models.Model):
    class Level(models.TextChoices):
        BEGINNER = "beginner", "Бастаушы"
        INTERMEDIATE = "intermediate", "Орта"
        ADVANCED = "advanced", "Жоғары"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    short_description = models.CharField(max_length=300)
    description = models.TextField()
    cover = models.ImageField(upload_to="courses/covers/", blank=True, null=True)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.BEGINNER)
    language = models.CharField(max_length=8, default="kk")
    duration_hours = models.PositiveIntegerField(default=20)
    authors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="authored_courses", blank=True
    )
    tags = models.CharField(max_length=255, blank=True, help_text="Үтірмен бөлінген тегтер")
    is_published = models.BooleanField(default=False)
    has_final_exam = models.BooleanField(default=True)
    final_exam_pass_pct = models.PositiveSmallIntegerField(default=70)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_published", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title) or f"course-{timezone.now().timestamp():.0f}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("courses:detail", args=[self.slug])

    @property
    def total_lessons(self):
        return Lesson.objects.filter(module__course=self).count()

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    has_test = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("course", "order")]

    def __str__(self):
        return f"{self.order}. {self.title}"


class Lesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    order = models.PositiveSmallIntegerField(default=0)
    summary = models.CharField(max_length=400, blank=True)
    # Block-based content: list of {type, value} dicts.
    # Types: heading, paragraph, video, image, quote, term, callout, list.
    content = models.JSONField(default=list, blank=True)
    video = models.FileField(upload_to="lessons/videos/", blank=True, null=True)
    video_url = models.URLField(blank=True, help_text="Сыртқы видео сілтемесі (YouTube және т.б.)")
    duration_minutes = models.PositiveSmallIntegerField(default=10)
    is_free_preview = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("module", "slug")]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            "courses:lesson",
            args=[self.module.course.slug, self.module.id, self.slug],
        )

    @property
    def course(self):
        return self.module.course

    def plain_text(self) -> str:
        """Flat textual representation for AI context."""
        parts = [self.title, self.summary]
        for block in self.content or []:
            v = block.get("value") if isinstance(block, dict) else None
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend(str(x) for x in v)
            elif isinstance(v, dict):
                parts.extend(str(x) for x in v.values() if isinstance(x, str))
        return "\n\n".join(p for p in parts if p)


class Enrollment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "course")]
        ordering = ["-enrolled_at"]

    def __str__(self):
        return f"{self.user} → {self.course}"

    def progress_pct(self) -> int:
        total = self.course.total_lessons
        if not total:
            return 0
        done = LessonProgress.objects.filter(
            user=self.user, lesson__module__course=self.course, completed_at__isnull=False
        ).count()
        return int(round(done * 100 / total))

    def completed_modules(self):
        completed = []
        for module in self.course.modules.all().prefetch_related("lessons"):
            lesson_ids = list(module.lessons.values_list("id", flat=True))
            if not lesson_ids:
                continue
            done = LessonProgress.objects.filter(
                user=self.user, lesson_id__in=lesson_ids, completed_at__isnull=False
            ).count()
            if done == len(lesson_ids):
                completed.append(module.id)
        return completed


class LessonProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_progress"
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    seconds_spent = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("user", "lesson")]
        ordering = ["-started_at"]


class Note(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes"
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="notes")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Note by {self.user} on {self.lesson}"
