from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "display_name", "role", "university", "year_of_study", "is_staff", "last_seen")
    list_filter = ("role", "university", "region", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Профиль",
            {
                "fields": (
                    "role", "avatar", "bio",
                    "university", "region", "specialty", "year_of_study",
                    "locale", "is_profile_public", "last_seen",
                )
            },
        ),
    )

    @admin.display(description="Аты-жөні")
    def display_name(self, obj):
        return obj.display_name
