import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret")

import pytest


@pytest.fixture(autouse=True)
def _plain_staticfiles(settings):
    """Admin pages need no collected-static manifest in tests."""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
