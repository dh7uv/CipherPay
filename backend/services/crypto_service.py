from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings

settings = get_settings()


def canonical_transaction_payload(transaction: dict) -> str:
    """Create the stable, security-relevant payload protected by the HMAC."""
    import json

    protected = {
        "transaction_id": transaction["transaction_id"],
        "user_id": transaction["user_id"],
        "amount": transaction["amount"],
        "currency": transaction["currency"],
        "created_at": transaction["created_at"],
    }
    return json.dumps(protected, sort_keys=True, separators=(",", ":"))


def _get_aes_key() -> bytes:
    key = settings.encryption_key
    try:
        decoded = base64.b64decode(key, validate=True)
        if len(decoded) in {16, 24, 32}:
            return decoded
    except Exception:
        pass
    if len(key.encode("utf-8")) in {16, 24, 32}:
        return key.encode("utf-8")
    return hashlib.sha256(key.encode("utf-8")).digest()


def encrypt_value(value: str) -> dict[str, str]:
    """Encrypt text into a MongoDB-safe AES-256-GCM container."""
    if not value:
        return {}
    nonce = os.urandom(12)
    encrypted = AESGCM(_get_aes_key()).encrypt(nonce, value.encode("utf-8"), None)
    ciphertext, tag = encrypted[:-16], encrypted[-16:]
    return {
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
    }


def decrypt_value(value: dict[str, str] | str) -> str:
    if not value:
        return ""
    if isinstance(value, str):  # Backward compatibility for existing encrypted records.
        payload = base64.b64decode(value)
        nonce, encrypted = payload[:12], payload[12:]
    else:
        nonce = base64.b64decode(value["nonce"])
        encrypted = base64.b64decode(value["ciphertext"]) + base64.b64decode(value["tag"])
    plaintext = AESGCM(_get_aes_key()).decrypt(nonce, encrypted, None)
    return plaintext.decode("utf-8")


def sign_hmac(payload: str) -> str:
    return hmac.new(settings.hmac_secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac(payload: str, signature: str) -> bool:
    expected = sign_hmac(payload)
    return hmac.compare_digest(expected, signature)


def verify_transaction_hmac(transaction: dict) -> bool:
    """Verify current records and legacy records created before canonical signing."""
    signature = transaction.get("integrity_hmac", "")
    if verify_hmac(canonical_transaction_payload(transaction), signature):
        return True
    import json

    legacy_payload = {key: value for key, value in transaction.items() if key != "integrity_hmac"}
    return verify_hmac(json.dumps(legacy_payload, sort_keys=True), signature)
