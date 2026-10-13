"""Encrypt the AI provider key with a key derived from DJANGO_SECRET_KEY."""
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings


def _fernet():
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"merit-badge ai provider key v1"
    ).derive(settings.SECRET_KEY.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(plain):
    return _fernet().encrypt(plain.encode()).decode() if plain else ""


def decrypt(token):
    """Return the key, or None if it is empty or cannot be read (the secret key changed)."""
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
