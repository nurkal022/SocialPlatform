from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.UstazLoginView.as_view(), name="login"),
    path("logout/", views.UstazLogoutView.as_view(), name="logout"),
    path("me/edit/", views.edit_profile, name="edit_profile"),
    path("u/<str:username>/", views.profile, name="profile"),
    path("become/<str:username>/", views.become, name="become"),
    path("become-exit/", views.exit_become, name="exit_become"),
]
