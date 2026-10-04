from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_transaction_submission():
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "securepass", "role": "user"},
    )
    assert register_response.status_code == 200

    transaction_response = client.post(
        "/api/v1/transactions/submit",
        json={
            "user_id": register_response.json()["user_id"],
            "amount": 2400,
            "currency": "USD",
            "merchant": "crypto",
            "device_id": "device-1",
            "location": "Berlin",
        },
    )
    assert transaction_response.status_code == 200
    payload = transaction_response.json()
    assert payload["risk"]["risk_category"] in {"Medium", "High", "Low"}
