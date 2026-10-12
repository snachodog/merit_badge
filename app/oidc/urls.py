from django.urls import path

from . import views

urlpatterns = [
    path("oidc/login/", views.oidc_login, name="oidc_login"),
    path("oidc/callback/", views.oidc_callback, name="oidc_callback"),
    path("oidc/link/", views.oidc_link, name="oidc_link"),
    path("oidc/unlink/", views.oidc_unlink, name="oidc_unlink"),
    path("settings/oidc/", views.oidc_settings, name="oidc_settings"),
    path("settings/oidc/test/", views.oidc_test, name="oidc_test"),
]
