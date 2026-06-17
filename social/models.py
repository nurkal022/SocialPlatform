from django.conf import settings
from django.db import models

from courses.models import Course, Lesson


class Comment(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_hidden = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["lesson", "created_at"])]

    def __str__(self):
        return f"{self.user}: {self.body[:40]}"


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liked_comments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("comment", "user")]


class CourseReview(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_reviews"
    )
    rating = models.PositiveSmallIntegerField()
    body = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("course", "user")]
        ordering = ["-created_at"]


class Report(models.Model):
    class Kind(models.TextChoices):
        COMMENT = "comment", "Пікір"
        REVIEW = "review", "Шолу"
        CASE = "case", "Кейс жауабы"
        LESSON = "lesson", "Сабақ"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    target_id = models.PositiveIntegerField()
    reason = models.TextField()
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["resolved", "-created_at"]
