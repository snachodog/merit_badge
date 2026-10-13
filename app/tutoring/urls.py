from django.urls import path

from . import views

urlpatterns = [
    path("settings/ai/", views.ai_settings, name="ai_settings"),
    path("settings/ai/test/", views.ai_test, name="ai_test"),
    path("tutor/", views.session_list, name="tutor_list"),
    path("tutor/start/<int:progress_pk>/", views.session_start, name="tutor_start"),
    path("tutor/<int:pk>/", views.session_detail, name="tutor_session"),
    path("tutor/<int:pk>/end/", views.session_end, name="tutor_end"),
    path("tutor/<int:pk>/keep/", views.session_keep, name="tutor_keep"),
    path("tutor/<int:pk>/discard/", views.session_discard, name="tutor_discard"),
]
