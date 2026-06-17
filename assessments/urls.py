from django.urls import path

from . import views

app_name = "assessments"

urlpatterns = [
    path("cases/", views.cases_catalog, name="cases"),
    path("cases/<int:case_id>/", views.case_detail, name="case_detail"),
    path("cases/<int:case_id>/submit/", views.case_submit, name="case_submit"),
    path("quiz/<int:quiz_id>/start/", views.quiz_start, name="quiz_start"),
    path("attempt/<int:attempt_id>/", views.attempt_take, name="attempt_take"),
    path("attempt/<int:attempt_id>/submit/", views.attempt_submit, name="attempt_submit"),
    path("attempt/<int:attempt_id>/result/", views.attempt_result, name="attempt_result"),
]
