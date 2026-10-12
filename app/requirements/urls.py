from django.urls import path

from . import views

urlpatterns = [
    path("versions/<int:pk>/", views.version_detail, name="version_detail"),
    path("versions/<int:pk>/edit/", views.version_edit, name="version_edit"),
    path("versions/<int:pk>/delete/", views.version_delete, name="version_delete"),
    path("versions/<int:pk>/details/", views.version_meta, name="version_meta"),
    path("versions/<int:pk>/nodes/add/", views.node_add, name="node_add"),
    path("versions/<int:pk>/<str:action>/", views.version_action, name="version_action"),
    path("nodes/<int:pk>/edit/", views.node_edit, name="node_edit"),
    path("nodes/<int:pk>/delete/", views.node_delete, name="node_delete"),
    path("nodes/<int:pk>/move/", views.node_move, name="node_move"),
    path("import/", views.import_program, name="import_program"),
]
