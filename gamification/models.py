import math

from django.conf import settings
from django.db import models


class Badge(models.Model):
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=8, default="🏅", help_text="Emoji")
    tier = models.PositiveSmallIntegerField(default=1, help_text="1=bronze, 2=silver, 3=gold, 4=platinum")
    threshold = models.PositiveIntegerField(default=1, help_text="Шарт мәні (XP, дней, кейстер ж.т.б.)")
    rule = models.CharField(
        max_length=32,
        default="lessons_completed",
        help_text="lessons_completed|xp_total|streak_days|cases_graded|quizzes_passed|courses_finished",
    )

    class Meta:
        ordering = ["tier", "name"]

    def __str__(self):
        return f"{self.icon} {self.name}"


class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges"
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="holders")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "badge")]
        ordering = ["-awarded_at"]


class XPLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="xp_logs"
    )
    amount = models.IntegerField()
    reason = models.CharField(max_length=64)
    ref = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]


class Streak(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streak"
    )
    current = models.PositiveIntegerField(default=0)
    longest = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    freezes_available = models.PositiveSmallIntegerField(default=2)
    freezes_used_month = models.PositiveSmallIntegerField(default=0)
    month_marker = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} — {self.current} күн"


class Profile(models.Model):
    """Cached gamification state for fast leaderboard queries."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gprofile"
    )
    xp = models.PositiveIntegerField(default=0)
    level = models.PositiveSmallIntegerField(default=1)
    weekly_xp = models.PositiveIntegerField(default=0)
    monthly_xp = models.PositiveIntegerField(default=0)
    last_week_reset = models.DateField(null=True, blank=True)
    last_month_reset = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} L{self.level} ({self.xp} XP)"

    @staticmethod
    def xp_for_level(level: int) -> int:
        """Exponential curve: lvl N requires 50 * N^1.6 XP cumulative."""
        return int(50 * (level ** 1.6))

    @staticmethod
    def level_for_xp(xp: int) -> int:
        # invert: lvl = (xp/50)^(1/1.6)
        if xp <= 0:
            return 1
        lvl = int((xp / 50) ** (1 / 1.6))
        return max(1, min(50, lvl))

    def xp_into_level(self):
        cur = self.xp_for_level(self.level)
        nxt = self.xp_for_level(self.level + 1)
        return self.xp - cur, nxt - cur


class WeeklyChallenge(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    target_xp = models.PositiveIntegerField(default=500)
    reward_xp = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["-starts_on"]

    def __str__(self):
        return self.title
