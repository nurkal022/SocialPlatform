from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import ensure_profile, ensure_streak

User = get_user_model()


@receiver(post_save, sender=User)
def init_user_gamification(sender, instance, created, **kwargs):
    if created:
        ensure_profile(instance)
        ensure_streak(instance)
