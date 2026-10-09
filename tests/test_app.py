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
    authorization = "Bearer " + register_response.json()["token"]

    transaction_response = client.post(
        "/api/v1/transactions/submit",
        headers={"Authorization": authorization},
        json={
            "user_id": register_response.json()["user_id"],
            "amount": 2400,
            "merchant_category": "Grocery",
            "payment_method": "UPI",
            "device_id": "device-1",
            "location": "Mumbai",
        },
    )
    assert transaction_response.status_code == 200
    payload = transaction_response.json()
    assert payload["risk"]["risk_category"] in {"Medium", "High", "Low"}
    assert "merchant" not in payload["transaction"]
    assert payload["transaction"]["merchant_category"] == "Grocery"
    assert payload["transaction"]["payment_method"] == "UPI"
    assert payload["transaction"]["currency"] == "INR"

    listed_transactions = client.get(
        "/api/v1/transactions/",
        headers={"Authorization": authorization},
    )
    listed_transaction = next(
        transaction
        for transaction in listed_transactions.json()["transactions"]
        if transaction["transaction_id"] == payload["transaction"]["transaction_id"]
    )
    assert listed_transaction["location_display"] == "Mumbai"
    assert isinstance(listed_transaction["location"], dict)
