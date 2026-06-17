from django.contrib import admin

from .models import AICallLog


@admin.register(AICallLog)
class AICallLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "purpose", "model", "total_tokens", "cost_usd", "latency_ms", "success")
    list_filter = ("purpose", "model", "success")
    search_fields = ("user__username", "ref", "error")
    readonly_fields = [f.name for f in AICallLog._meta.fields]
    date_hierarchy = "created_at"
