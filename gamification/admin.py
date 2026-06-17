from django.contrib import admin

from .models import Badge


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "rule", "threshold", "tier")
    list_filter = ("tier", "rule")
    search_fields = ("name", "code")
