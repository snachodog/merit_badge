from django.urls import path

from . import views

urlpatterns = [
    path("learning/", views.my_learning, name="my_learning"),
    path("versions/<int:pk>/start/", views.plan_start, name="plan_start"),
    path("learning/<int:pk>/", views.plan_detail, name="plan_detail"),
    path("learning/<int:pk>/complete/", views.plan_complete, name="plan_complete"),
    path("learning/<int:pk>/condition/", views.plan_condition, name="plan_condition"),
    path("learning/<int:pk>/<str:action>/", views.plan_action, name="plan_action"),
    path("progress/<int:pk>/", views.progress_detail, name="progress_detail"),
    path("progress/<int:pk>/status/", views.progress_status, name="progress_status"),
    path("progress/<int:pk>/check/", views.progress_check, name="progress_check"),
    path("progress/<int:pk>/prior/", views.progress_prior, name="progress_prior"),
    path("progress/<int:pk>/notes/", views.progress_notes, name="progress_notes"),
    path("progress/<int:pk>/attest/", views.progress_attest, name="progress_attest"),
]
