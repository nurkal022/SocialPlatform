"""Seed current week's challenge if absent."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from gamification.models import WeeklyChallenge


CHALLENGES_POOL = [
    ("Аптаның марафоны: 500 XP", "Бұл апта ішінде 500 XP жинаңыз. Сабақтар, тесттер мен кейстерден ұпай аласыз.", 500, 100),
    ("Білімпаз: 800 XP апта ішінде", "Үнемі оқыған студентке арналған. 800 XP жинасаңыз — 150 бонус XP.", 800, 150),
    ("Үш күн қатарынан streak", "Streak-ке үш күн қатарынан кіріңіз. Бонус — Streak Гладиатор белгісі.", 200, 75),
    ("Әдіскер: 3 кейс", "Аптада 3 кейс тапсырыңыз. Әр кейс ИИ бағалайды.", 300, 120),
]


class Command(BaseCommand):
    help = "Seed current week's challenge if none active"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Replace current week's challenge")

    def handle(self, *args, **opts):
        today = timezone.now().date()
        # Monday of this week → Sunday
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)

        existing = WeeklyChallenge.objects.filter(starts_on=start, ends_on=end).first()
        if existing and not opts["force"]:
            self.stdout.write(self.style.WARNING(
                f"Challenge already exists for {start} → {end}: «{existing.title}». Use --force to replace."
            ))
            return
        if existing:
            existing.delete()

        # Pick by week-number deterministically so re-run is stable
        week_num = today.isocalendar().week
        title, desc, target, reward = CHALLENGES_POOL[week_num % len(CHALLENGES_POOL)]
        ch = WeeklyChallenge.objects.create(
            title=title, description=desc,
            starts_on=start, ends_on=end,
            target_xp=target, reward_xp=reward,
        )
        self.stdout.write(self.style.SUCCESS(
            f"✓ Created challenge «{ch.title}» ({start} → {end}, target={target} XP)"
        ))
