from django.urls import path

from . import views

urlpatterns = [
    path("settings/invitations/new/", views.invitation_create, name="invitation_create"),
    path("settings/invitations/<int:pk>/revoke/", views.invitation_revoke, name="invitation_revoke"),
    path("invite/<str:token>/", views.invitation_accept, name="invitation_accept"),
]
