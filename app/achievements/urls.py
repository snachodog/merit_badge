from django.urls import path

from . import views

urlpatterns = [
    path("achievements/", views.achievement_list, name="achievement_list"),
    path("achievements/<int:pk>/certificate/", views.certificate, name="certificate"),
]
