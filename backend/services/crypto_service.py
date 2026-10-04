from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings

settings = get_settings()


def _get_aes_key() -> bytes:
    return base64.b64decode(settings.encryption_key)


def encrypt_value(value: str) -> str:
    nonce = hashlib.sha256(value.encode("utf-8")).digest()[:12]
    ciphertext = AESGCM(_get_aes_key()).encrypt(nonce, value.encode("utf-8"), None)
    return base64.b64encode(ciphertext).decode("utf-8")


def decrypt_value(value: str) -> str:
    ciphertext = base64.b64decode(value)
    nonce = hashlib.sha256(value.encode("utf-8")).digest()[:12]
    plaintext = AESGCM(_get_aes_key()).decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def sign_hmac(payload: str) -> str:
    return hmac.new(settings.hmac_secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac(payload: str, signature: str) -> bool:
    expected = sign_hmac(payload)
    return hmac.compare_digest(expected, signature)
