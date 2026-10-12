from django.urls import path

from . import views

urlpatterns = [
    path("settings/users/", views.user_list, name="user_list"),
    path("settings/users/<int:pk>/role/", views.user_role, name="user_role"),
    path("settings/users/<int:pk>/active/", views.user_active, name="user_active"),
    path("settings/users/<int:pk>/password/", views.user_password, name="user_password"),
]
