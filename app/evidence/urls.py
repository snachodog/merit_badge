from django.urls import path

from . import views

urlpatterns = [
    path("evidence/<int:pk>/file/", views.download, name="evidence_download"),
    path("evidence/<int:pk>/delete/", views.evidence_delete, name="evidence_delete"),
    path("evidence/<int:pk>/observed/", views.evidence_observe, name="evidence_observe"),
    path("progress/<int:pk>/evidence/<str:kind>/", views.evidence_add, name="evidence_add"),
]
