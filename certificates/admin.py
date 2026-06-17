from django.contrib import admin

from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("full_name_snapshot", "course", "final_score_pct", "issued_at", "uid")
    search_fields = ("full_name_snapshot", "user__username", "uid")
    list_filter = ("course",)
    readonly_fields = ("uid", "issued_at", "pdf")
