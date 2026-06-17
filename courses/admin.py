from django.contrib import admin

from .models import Course, Lesson, Module


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("order", "title", "slug", "duration_minutes", "is_free_preview")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("order",)


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ("order", "title", "has_test")
    ordering = ("order",)
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "language", "is_published", "duration_hours", "updated_at")
    list_filter = ("is_published", "level", "language")
    search_fields = ("title", "description", "tags")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("authors",)
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("course", "order", "title", "has_test")
    list_filter = ("course",)
    list_editable = ("order", "has_test")
    inlines = [LessonInline]
    ordering = ("course", "order")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("module", "order", "title", "duration_minutes", "is_free_preview")
    list_filter = ("module__course",)
    list_editable = ("order", "is_free_preview")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title",)
