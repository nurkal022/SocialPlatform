from django.urls import path

from . import views

app_name = "certificates"

urlpatterns = [
    path("verify/<uuid:uid>/", views.verify, name="verify"),
    path("<uuid:uid>/", views.detail, name="detail"),
    path("<uuid:uid>/download/", views.download, name="download"),
]
