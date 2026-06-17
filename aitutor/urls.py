from django.urls import path

from . import views

app_name = "aitutor"

urlpatterns = [
    path("tutor/<int:lesson_id>/", views.tutor_panel, name="tutor"),
    path("tutor/<int:lesson_id>/send/", views.tutor_send, name="tutor_send"),
    path("msg/<int:message_id>/rate/", views.rate_message, name="rate"),
    path("practice/<int:lesson_id>/", views.practice, name="practice"),
]
