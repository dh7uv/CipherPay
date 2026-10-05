import base64

import pytest
from cryptography.exceptions import InvalidTag

from backend.services.crypto_service import decrypt_value, encrypt_value, sign_hmac, verify_hmac


def test_encrypted_values_round_trip_with_unique_nonces():
    first = encrypt_value("Berlin")
    second = encrypt_value("Berlin")

    assert first["nonce"] != second["nonce"]
    assert len(base64.b64decode(first["nonce"])) == 12
    assert len(base64.b64decode(first["tag"])) == 16
    assert first["ciphertext"] != "Berlin"
    assert decrypt_value(first) == "Berlin"
    assert decrypt_value(second) == "Berlin"


def test_encrypted_value_tampering_is_rejected():
    encrypted = encrypt_value("Berlin")
    encrypted["ciphertext"] = base64.b64encode(b"London").decode("ascii")

    with pytest.raises(InvalidTag):
        decrypt_value(encrypted)


def test_encrypted_value_requires_nonce_ciphertext_and_tag():
    with pytest.raises(ValueError, match="nonce, ciphertext, and tag"):
        decrypt_value({"ciphertext": "YmVybGlu"})


def test_hmac_detects_payload_tampering():
    signature = sign_hmac('{"amount":100}')

    assert verify_hmac('{"amount":100}', signature)
    assert not verify_hmac('{"amount":101}', signature)
