from django.conf import settings
from django.db import models


class AICallLog(models.Model):
    class Purpose(models.TextChoices):
        TUTOR = "tutor", "ИИ-тутор"
        CASE = "case", "Кейс бағалау"
        SHORT = "short", "Қысқа жауап"
        PRACTICE = "practice", "Жаттығу сұрақтары"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_calls",
    )
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    model = models.CharField(max_length=64)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    ref = models.CharField(max_length=128, blank=True, help_text="e.g. lesson:42 or case:7")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.purpose} {self.model} {self.total_tokens}tok"


class TutorMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Пайдаланушы"
        ASSISTANT = "assistant", "ИИ"
        SYSTEM = "system", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutor_messages"
    )
    lesson = models.ForeignKey(
        "courses.Lesson", on_delete=models.SET_NULL, null=True, blank=True, related_name="tutor_messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    rating = models.SmallIntegerField(default=0, help_text="-1 / 0 / +1")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["user", "lesson", "created_at"])]
