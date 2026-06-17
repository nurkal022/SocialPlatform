from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "reporter", "kind", "target_id", "resolved")
    list_filter = ("kind", "resolved")
