from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse


class University(models.Model):
    name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=32, blank=True)
    city = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name


class Region(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Specialty(models.Model):
    code = models.CharField(max_length=16, blank=True)
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Specialties"

    def __str__(self):
        return f"{self.code} {self.name}".strip()


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Студент"
        METHODIST = "methodist", "Методист"
        ADMIN = "admin", "Әкімші"

    email = models.EmailField(blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True)
    university = models.ForeignKey(
        University, on_delete=models.SET_NULL, null=True, blank=True, related_name="students"
    )
    region = models.ForeignKey(
        Region, on_delete=models.SET_NULL, null=True, blank=True, related_name="users"
    )
    specialty = models.ForeignKey(
        Specialty, on_delete=models.SET_NULL, null=True, blank=True, related_name="users"
    )
    year_of_study = models.PositiveSmallIntegerField(null=True, blank=True)
    locale = models.CharField(max_length=8, default="kk")
    is_profile_public = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    REQUIRED_FIELDS = []

    def __str__(self):
        return self.get_full_name() or self.username

    def get_absolute_url(self):
        return reverse("accounts:profile", args=[self.username])

    @property
    def is_methodist(self):
        return self.role == self.Role.METHODIST or self.is_staff

    @property
    def display_name(self):
        return self.get_full_name() or self.username
