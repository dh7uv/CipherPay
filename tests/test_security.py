from fastapi.testclient import TestClient

from backend.main import app
from backend.services.crypto_service import decrypt_value, encrypt_value
from backend.services.fraud_engine import score_transaction


def analyst_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "demo@cipherpay.local", "password": "demo123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_sensitive_values_are_encrypted_with_unique_nonces():
    first = encrypt_value("Berlin")
    second = encrypt_value("Berlin")
    assert first != second
    assert decrypt_value(first) == "Berlin"
    assert decrypt_value(second) == "Berlin"


def test_integrity_verification_detects_tampering():
    with TestClient(app) as client:
        headers = analyst_headers(client)
        response = client.post(
            "/api/v1/transactions",
            headers=headers,
            json={"user_id": "demo-user", "amount": 200, "currency": "USD", "merchant": "books", "device_id": "test-device", "location": "Berlin"},
        )
        assert response.status_code == 200
        transaction_id = response.json()["transaction"]["transaction_id"]

        verified = client.post(f"/api/v1/transactions/{transaction_id}/verify-integrity", headers=headers)
        assert verified.json()["integrity_valid"] is True

        transaction = next(item for item in app.state.store["transactions"] if item["transaction_id"] == transaction_id)
        transaction["amount"] = 999_999
        tampered = client.post(f"/api/v1/transactions/{transaction_id}/verify-integrity", headers=headers)
        assert tampered.json()["integrity_valid"] is False


def test_analyst_can_inspect_decrypted_transaction_metadata():
    with TestClient(app) as client:
        headers = analyst_headers(client)
        submitted = client.post(
            "/api/v1/transactions",
            headers=headers,
            json={"user_id": "demo-user", "amount": 120, "currency": "USD", "merchant": "books", "device_id": "inspect-device", "location": "Berlin"},
        )
        transaction_id = submitted.json()["transaction"]["transaction_id"]
        response = client.get(f"/api/v1/transactions/{transaction_id}/details", headers=headers)

    assert response.status_code == 200
    assert response.json()["sensitive_metadata"] == {"device_id": "inspect-device", "location": "Berlin"}


def test_analyst_endpoints_reject_regular_users():
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={"email": "regular@example.com", "password": "securepass"})
        headers = {"Authorization": f"Bearer {response.json()['token']}"}
        assert client.get("/api/v1/alerts", headers=headers).status_code == 403
        assert client.get("/api/v1/analytics/summary", headers=headers).status_code == 403


def test_rule_engine_discloses_ml_fallback_when_model_is_absent():
    risk = score_transaction({"user_id": "rules-user", "amount": 1, "merchant": "books", "device_id": "rules-device"})
    assert risk["risk_category"] == "Low"
    assert any("fallback" in reason.lower() for reason in risk["risk_reasons"])
