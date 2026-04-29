from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

SECRET_PREFIX = "enc:v1:"


def encrypt_secret(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    if cleaned.startswith(SECRET_PREFIX):
        return cleaned
    token = _fernet().encrypt(cleaned.encode("utf-8")).decode("utf-8")
    return f"{SECRET_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    if not cleaned.startswith(SECRET_PREFIX):
        return cleaned
    token = cleaned.removeprefix(SECRET_PREFIX)
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Encrypted secret could not be decrypted with the configured key.") from exc


def mask_secret(value: str | None) -> str | None:
    cleaned = decrypt_secret(value)
    if not cleaned:
        return None
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]}"


def is_encrypted_secret(value: str | None) -> bool:
    return bool(value and value.strip().startswith(SECRET_PREFIX))


def _fernet() -> Fernet:
    secret = get_settings().secret_encryption_key.strip()
    if not secret:
        secret = "dev-secret-encryption-key-change-me"
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))
