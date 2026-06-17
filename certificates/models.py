import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse

from courses.models import Course


class Certificate(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificates"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    final_score_pct = models.PositiveSmallIntegerField(default=0)
    issued_at = models.DateTimeField(auto_now_add=True)
    full_name_snapshot = models.CharField(max_length=200)
    pdf = models.FileField(upload_to="certificates/", blank=True, null=True)

    class Meta:
        unique_together = [("user", "course")]
        ordering = ["-issued_at"]

    def __str__(self):
        return f"{self.full_name_snapshot} — {self.course} ({self.issued_at:%Y-%m-%d})"

    def get_verify_url(self):
        return reverse("certificates:verify", args=[str(self.uid)])

    def get_absolute_url(self):
        return reverse("certificates:detail", args=[str(self.uid)])
