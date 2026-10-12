from django.urls import path

from . import views

urlpatterns = [
    path("catalog/", views.catalog, name="catalog"),
    path("programs/new/", views.program_create, name="program_create"),
    path("programs/<int:pk>/", views.program_detail, name="program_detail"),
    path("programs/<int:pk>/sharing/", views.program_sharing, name="program_sharing"),
    path("programs/<int:pk>/awards/new/", views.award_create, name="award_create"),
    path("awards/<int:pk>/", views.award_detail, name="award_detail"),
    path("awards/<int:pk>/versions/new/", views.version_create, name="version_create"),
]
