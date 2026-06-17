from django.urls import path

from . import views
from . import views_studio as vs

app_name = "courses"

urlpatterns = [
    path("", views.catalog, name="catalog"),

    # ---- Studio (methodist content editor) ----
    path("studio/", vs.dashboard, name="studio_dashboard"),
    path("studio/create/", vs.course_create, name="studio_course_create"),
    path("studio/c/<slug:slug>/", vs.course_edit, name="studio_course"),
    path("studio/c/<slug:slug>/update/", vs.course_update, name="studio_course_update"),
    path("studio/c/<slug:slug>/delete/", vs.course_delete, name="studio_course_delete"),
    path("studio/c/<slug:slug>/module/add/", vs.module_add, name="studio_module_add"),
    path("studio/m/<int:module_id>/update/", vs.module_update, name="studio_module_update"),
    path("studio/m/<int:module_id>/delete/", vs.module_delete, name="studio_module_delete"),
    path("studio/m/<int:module_id>/lesson/add/", vs.lesson_add, name="studio_lesson_add"),
    path("studio/l/<int:lesson_id>/", vs.lesson_edit, name="studio_lesson"),
    path("studio/l/<int:lesson_id>/update/", vs.lesson_update, name="studio_lesson_update"),
    path("studio/l/<int:lesson_id>/delete/", vs.lesson_delete, name="studio_lesson_delete"),

    # Quiz editor
    path("studio/quiz/m/<int:module_id>/", vs.quiz_module_edit, name="studio_quiz_module"),
    path("studio/quiz/f/<slug:course_slug>/", vs.quiz_final_edit, name="studio_quiz_final"),
    path("studio/quiz/<int:quiz_id>/update/", vs.quiz_update, name="studio_quiz_update"),
    path("studio/quiz/<int:quiz_id>/question/add/", vs.question_add, name="studio_question_add"),
    path("studio/q/<int:question_id>/update/", vs.question_update, name="studio_question_update"),
    path("studio/q/<int:question_id>/delete/", vs.question_delete, name="studio_question_delete"),

    path("studio/reorder/", vs.reorder, name="studio_reorder"),

    # ---- Public catalog routes ----
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/enroll/", views.enroll, name="enroll"),
    path(
        "<slug:course_slug>/m<int:module_id>/<slug:lesson_slug>/",
        views.lesson_view,
        name="lesson",
    ),
    path("lesson/<int:lesson_id>/complete/", views.complete_lesson, name="complete_lesson"),
    path("lesson/<int:lesson_id>/note/", views.save_note, name="save_note"),
]
