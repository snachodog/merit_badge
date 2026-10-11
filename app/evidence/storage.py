"""Storage abstraction for private evidence files.

Callers use `get_storage()` only. The default backend writes under
MEDIA_ROOT/evidence (settings.STORAGES["evidence"]). There is no MEDIA_URL and
no web route to these files except the owner-checked download view.
Another backend (for example S3-compatible) can replace it in settings.
"""
from django.core.files.storage import storages


def get_storage():
    return storages["evidence"]


def delete_file(storage_key):
    """Remove a stored file. Missing files are fine."""
    if not storage_key:
        return
    try:
        get_storage().delete(storage_key)
    except OSError:  # pragma: no cover - logged by caller context; never block a delete
        import logging

        logging.getLogger(__name__).exception("Could not remove evidence file %s", storage_key)
