from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        self._patch_admin_index()

    def _patch_admin_index(self):
        from django.contrib import admin
        from django.db.models import Sum
        from django.utils import timezone

        original_index = admin.site.index

        def patched_index(request, extra_context=None):
            from accounts.models import User
            from aitutor.models import AICallLog
            from assessments.models import CaseStudy, CaseSubmission
            from certificates.models import Certificate
            from courses.models import Course, Lesson

            today = timezone.now().date()
            month_start = today.replace(day=1)

            stats = {
                "courses": Course.objects.count(),
                "lessons": Lesson.objects.count(),
                "students": User.objects.filter(role="student").count(),
                "cases": CaseStudy.objects.count(),
                "certificates": Certificate.objects.count(),
                "case_submissions": CaseSubmission.objects.count(),
                "ai_calls_today": AICallLog.objects.filter(created_at__date=today).count(),
                "ai_cost_month": AICallLog.objects.filter(
                    created_at__date__gte=month_start
                ).aggregate(s=Sum("cost_usd"))["s"] or 0,
            }
            recent_lessons = list(
                Lesson.objects.select_related("module").order_by("-updated_at")[:6]
            )
            recent_users = list(User.objects.order_by("-date_joined")[:6])

            ctx = {
                "stats": stats,
                "recent_lessons": recent_lessons,
                "recent_users": recent_users,
            }
            if extra_context:
                ctx.update(extra_context)
            return original_index(request, extra_context=ctx)

        admin.site.index = patched_index
