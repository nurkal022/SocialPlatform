from django.urls import path

from . import views

app_name = "social"

urlpatterns = [
    path("lesson/<int:lesson_id>/comment/", views.add_comment, name="add_comment"),
    path("comment/<int:comment_id>/like/", views.like_comment, name="like_comment"),
    path("course/<slug:course_slug>/review/", views.add_review, name="add_review"),
    path("report/<str:kind>/<int:target_id>/", views.report, name="report"),
    path("best/", views.best_solutions, name="best_solutions"),
]
