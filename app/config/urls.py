from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from config.core import views

# No registration or password-self-service routes: accounts are created by an
# administrator (see README bootstrap).
urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("settings/", views.settings_page, name="settings"),
    path("settings/export.json", views.export_json, name="export_json"),
    path("settings/evidence-files.zip", views.export_evidence_zip, name="export_evidence_zip"),
    path("", include("accounts.urls")),
    path("", include("oidc.urls")),
    path("", include("invitations.urls")),
    path("", include("programs.urls")),
    # learning before requirements: "versions/<pk>/start/" must not match the version actions.
    path("", include("learning.urls")),
    path("", include("requirements.urls")),
    path("", include("evidence.urls")),
    path("", include("achievements.urls")),
]
