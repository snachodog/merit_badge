from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from . import storage
from .models import EvidenceRecord


@receiver(post_delete, sender=EvidenceRecord)
def remove_file_after_delete(sender, instance, **kwargs):
    """Also covers cascades, such as deleting a whole plan or account."""
    key = instance.storage_key
    if key:
        transaction.on_commit(lambda: storage.delete_file(key))
