from django.contrib import admin

from .models import CaseStudy, CaseSubmission, Choice, Question, Quiz


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    fields = ("order", "kind", "text", "explanation", "points", "payload")
    ordering = ("order",)
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "kind", "module", "pass_pct", "is_published")
    list_filter = ("course", "kind", "is_published")
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("quiz", "order", "kind", "text", "points")
    list_filter = ("quiz", "kind")
    inlines = [ChoiceInline]


@admin.register(CaseStudy)
class CaseStudyAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "module", "difficulty", "is_published")
    list_filter = ("course", "difficulty", "is_published")
    search_fields = ("title", "situation")


@admin.register(CaseSubmission)
class CaseSubmissionAdmin(admin.ModelAdmin):
    list_display = ("user", "case", "score", "status", "is_public", "submitted_at")
    list_filter = ("status", "is_public", "case__course")
    readonly_fields = ("criteria_scores",)
