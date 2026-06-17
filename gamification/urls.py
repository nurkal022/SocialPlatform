from django.urls import path

from . import views

app_name = "gamification"

urlpatterns = [
    path("leaderboard/", views.leaderboard_view, name="leaderboard"),
    path("badges/", views.badges_index, name="badges"),
    path("me/", views.my_progress, name="me"),
]
