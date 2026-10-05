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
        headers={"Authorization": f"Bearer {register_response.json()['token']}"},
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


def test_transaction_requires_authentication():
    response = client.get("/api/v1/transactions/")
    assert response.status_code == 401


def test_analytics_summary_exposes_monitoring_metrics():
    with TestClient(app) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={"email": "demo@cipherpay.local", "password": "demo123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        response = test_client.get("/api/v1/analytics/summary", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["risk_trend"]) == 7
    assert set(payload["decision_distribution"]) == {"Approved", "Under Review", "Declined"}
    assert "security_metrics" in payload


def test_guest_session_is_read_only_but_can_view_monitoring_data():
    with TestClient(app) as test_client:
        guest_login = test_client.post("/api/v1/auth/guest")
        assert guest_login.status_code == 200
        headers = {"Authorization": f"Bearer {guest_login.json()['token']}"}
        summary = test_client.get("/api/v1/analytics/summary", headers=headers)
        transactions = test_client.get("/api/v1/transactions?page_size=10", headers=headers)
        submission = test_client.post(
            "/api/v1/transactions",
            headers=headers,
            json={"amount": 25, "currency": "USD", "merchant": "books"},
        )

    assert summary.status_code == 200
    assert transactions.status_code == 200
    assert transactions.json()["total"] >= 1
    assert submission.status_code == 403
