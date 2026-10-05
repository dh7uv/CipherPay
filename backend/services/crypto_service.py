from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings

settings = get_settings()
NONCE_LENGTH = 12
TAG_LENGTH = 16


def _get_aes_key() -> bytes:
    try:
        key = base64.b64decode(settings.encryption_key, validate=True)
    except ValueError as error:
        raise ValueError("ENCRYPTION_KEY must be valid base64") from error

    if len(key) != 32:
        raise ValueError("ENCRYPTION_KEY must decode to exactly 32 bytes")
    return key


def encrypt_value(value: str) -> dict[str, str]:
    nonce = secrets.token_bytes(NONCE_LENGTH)
    encrypted = AESGCM(_get_aes_key()).encrypt(nonce, value.encode("utf-8"), None)
    ciphertext, tag = encrypted[:-TAG_LENGTH], encrypted[-TAG_LENGTH:]

    return {
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
    }


def decrypt_value(value: dict[str, Any]) -> str:
    try:
        nonce = base64.b64decode(value["nonce"], validate=True)
        ciphertext = base64.b64decode(value["ciphertext"], validate=True)
        tag = base64.b64decode(value["tag"], validate=True)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Encrypted value must contain valid nonce, ciphertext, and tag fields") from error

    if len(nonce) != NONCE_LENGTH or len(tag) != TAG_LENGTH:
        raise ValueError("Encrypted value contains an invalid nonce or authentication tag")

    plaintext = AESGCM(_get_aes_key()).decrypt(nonce, ciphertext + tag, None)
    return plaintext.decode("utf-8")


def sign_hmac(payload: str) -> str:
    return hmac.new(settings.hmac_secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac(payload: str, signature: str) -> bool:
    expected = sign_hmac(payload)
    return hmac.compare_digest(expected, signature)


def transaction_integrity_payload(transaction: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in transaction.items()
        if key not in {"_id", "integrity_hmac"}
    }


def sign_transaction(transaction: dict[str, Any]) -> str:
    payload = json.dumps(transaction_integrity_payload(transaction), sort_keys=True)
    return sign_hmac(payload)


def verify_transaction_integrity(transaction: dict[str, Any]) -> bool:
    signature = transaction.get("integrity_hmac")
    if not isinstance(signature, str):
        return False
    payload = json.dumps(transaction_integrity_payload(transaction), sort_keys=True)
    return verify_hmac(payload, signature)
