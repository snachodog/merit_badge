from django.urls import path

from . import views

urlpatterns = [
    path("evidence/<int:pk>/file/", views.download, name="evidence_download"),
]
