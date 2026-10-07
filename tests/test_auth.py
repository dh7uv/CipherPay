import hashlib

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routes import auth as auth_routes
from backend.routes import transactions as transaction_routes
from backend.services import transaction_integrity
from backend.services.auth_service import create_access_token, hash_password
from backend.services.crypto_service import verify_transaction_integrity
from backend.services.redis_service import redis_service

client = TestClient(app)


def register_user(email: str, role: str = "user") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass", "role": role},
    )
    assert response.status_code == 200
    return response.json()


def test_login_accepts_case_insensitive_email_and_returns_authentication_token():
    user = register_user("login-check@example.com")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "  LOGIN-CHECK@EXAMPLE.COM ", "password": "securepass"},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == user["user_id"]
    assert response.json()["email"] == "login-check@example.com"
    assert response.json()["role"] == "user"
    assert response.json()["token"]


def test_login_rejects_wrong_password_and_suspended_account():
    user = register_user("login-denied@example.com")

    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "incorrect"},
    )
    stored_user = next(item for item in app.state.store["users"] if item["_id"] == user["user_id"])
    stored_user["status"] = "suspended"
    suspended = client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "securepass"},
    )

    assert wrong_password.status_code == 401
    assert suspended.status_code == 403


def transaction_payload(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "amount": 50,
        "currency": "USD",
        "merchant": "bookshop",
        "device_id": "device-test",
        "location": "Berlin",
    }


@pytest.mark.parametrize("decision", ["Approved", "Declined"])
def test_analyst_can_decide_high_risk_transaction_after_integrity_check(decision, monkeypatch):
    analyst = {
        "_id": "manual-review-analyst",
        "email": "manual-review-analyst@example.com",
        "password_hash": hash_password("securepass"),
        "role": "analyst",
        "status": "active",
    }
    app.state.store["users"].append(analyst)
    persisted_updates = []

    async def record_update(collection_name, transaction_id, changes):
        persisted_updates.append((collection_name, transaction_id, changes))

    monkeypatch.setattr(transaction_routes, "update_document", record_update)
    headers = {"Authorization": f"Bearer {create_access_token(analyst['_id'])}"}
    user = register_user("manual-review-owner@example.com")
    submitted = client.post(
        "/api/v1/transactions/submit",
        headers={"Authorization": f"Bearer {user['token']}"},
        json={
            **transaction_payload(user["user_id"]),
            "amount": 6000,
            "merchant": "crypto",
        },
    )
    transaction_id = submitted.json()["transaction"]["transaction_id"]

    verification = client.post(
        f"/api/v1/transactions/{transaction_id}/verify-integrity",
        headers=headers,
    )
    verified_transaction = next(
        item for item in app.state.store["transactions"]
        if item["transaction_id"] == transaction_id
    )
    verified_signature = verified_transaction["integrity_hmac"]
    verified_listing = client.get("/api/v1/transactions/", headers=headers)
    decision_response = client.post(
        f"/api/v1/transactions/{transaction_id}/decision",
        headers=headers,
        json={"decision": decision},
    )
    stored_transaction = next(
        item for item in app.state.store["transactions"]
        if item["transaction_id"] == transaction_id
    )

    assert submitted.json()["transaction"]["risk_score"] >= 70
    assert verification.json()["integrity_valid"] is True
    assert verification.json()["integrity_status"] == "Verified"
    assert verification.json()["manual_review_available"] is True
    assert verified_transaction["integrity_status"] == "Verified"
    assert verified_transaction["integrity_verified_by"] == analyst["_id"]
    assert any(
        item["transaction_id"] == transaction_id
        and item["integrity_status"] == "Verified"
        for item in verified_listing.json()["transactions"]
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["transaction"]["status"] == decision
    assert decision_response.json()["transaction"]["integrity_status"] == "Verified"
    assert decision_response.json()["transaction"]["reviewed_by"] == analyst["_id"]
    assert verify_transaction_integrity(stored_transaction)
    assert len(persisted_updates) == 2
    collection_name, persisted_id, verification_changes = persisted_updates[0]
    assert collection_name == "transactions"
    assert persisted_id == transaction_id
    assert verification_changes["integrity_status"] == "Verified"
    assert verification_changes["integrity_verified_by"] == analyst["_id"]
    assert verification_changes["integrity_hmac"] == verified_signature
    collection_name, persisted_id, changes = persisted_updates[1]
    assert collection_name == "transactions"
    assert persisted_id == transaction_id
    assert changes["status"] == decision
    assert changes["integrity_hmac"] == stored_transaction["integrity_hmac"]
    assert any(
        event["action"] == f"TRANSACTION_{decision.upper()}"
        and event["resource_id"] == transaction_id
        for event in app.state.store["audit_logs"]
    )


def test_manual_decision_rejects_tampered_and_non_high_risk_transactions():
    analyst = {
        "_id": "manual-review-guard-analyst",
        "email": "manual-review-guard@example.com",
        "password_hash": hash_password("securepass"),
        "role": "analyst",
        "status": "active",
    }
    app.state.store["users"].append(analyst)
    headers = {"Authorization": f"Bearer {create_access_token(analyst['_id'])}"}
    user = register_user("manual-review-guard-owner@example.com")
    user_headers = {"Authorization": f"Bearer {user['token']}"}
    low_risk = client.post(
        "/api/v1/transactions/submit",
        headers=user_headers,
        json=transaction_payload(user["user_id"]),
    ).json()["transaction"]
    high_risk = client.post(
        "/api/v1/transactions/submit",
        headers=user_headers,
        json={
            **transaction_payload(user["user_id"]),
            "amount": 6000,
            "merchant": "crypto",
        },
    ).json()["transaction"]
    next(
        item for item in app.state.store["transactions"]
        if item["transaction_id"] == high_risk["transaction_id"]
    )["amount"] = 1

    low_decision = client.post(
        f"/api/v1/transactions/{low_risk['transaction_id']}/decision",
        headers=headers,
        json={"decision": "Declined"},
    )
    tampered_decision = client.post(
        f"/api/v1/transactions/{high_risk['transaction_id']}/decision",
        headers=headers,
        json={"decision": "Approved"},
    )

    assert low_decision.status_code == 409
    assert tampered_decision.status_code == 409


@pytest.mark.parametrize("decision", ["Approved", "Declined"])
def test_analyst_can_decide_medium_risk_transaction_after_verification(decision, monkeypatch):
    analyst = {
        "_id": "medium-review-analyst",
        "email": "medium-review-analyst@example.com",
        "password_hash": hash_password("securepass"),
        "role": "analyst",
        "status": "active",
    }
    app.state.store["users"].append(analyst)
    monkeypatch.setattr(
        transaction_routes,
        "score_transaction",
        lambda payload, velocity_count, device_activity_count: {
            "risk_score": 55,
            "risk_category": "Medium",
            "risk_reasons": [
                f"Moderate transaction risk at {payload['merchant']}",
                f"Velocity {velocity_count}",
                f"Device activity {device_activity_count}",
            ],
        },
    )
    headers = {"Authorization": "Bearer " + create_access_token(analyst["_id"])}
    user = register_user("medium-review-owner@example.com")
    submitted = client.post(
        "/api/v1/transactions/submit",
        headers={"Authorization": "Bearer " + create_access_token(user["user_id"])},
        json={
            **transaction_payload(user["user_id"]),
            "amount": 2500,
            "merchant": "crypto",
        },
    ).json()["transaction"]
    transaction_id = submitted["transaction_id"]

    unverified_decision = client.post(
        f"/api/v1/transactions/{transaction_id}/decision",
        headers=headers,
        json={"decision": decision},
    )
    verification = client.post(
        f"/api/v1/transactions/{transaction_id}/verify-integrity",
        headers=headers,
    )
    decision_response = client.post(
        f"/api/v1/transactions/{transaction_id}/decision",
        headers=headers,
        json={"decision": decision},
    )

    assert submitted["risk_score"] < 70
    assert submitted["status"] == "Under Review"
    assert unverified_decision.status_code == 409
    assert verification.json()["integrity_valid"] is True
    assert verification.json()["manual_review_available"] is True
    assert decision_response.status_code == 200
    assert decision_response.json()["transaction"]["status"] == decision


def test_regular_user_cannot_make_manual_transaction_decision():
    user = register_user("manual-review-user@example.com")

    response = client.post(
        "/api/v1/transactions/example/decision",
        headers={"Authorization": f"Bearer {user['token']}"},
        json={"decision": "Approved"},
    )

    assert response.status_code == 403


def test_transaction_routes_require_a_valid_token():
    response = client.get("/api/v1/transactions/")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_registered_user_can_submit_and_only_list_own_transactions():
    user = register_user("auth-user@example.com")
    headers = {"Authorization": f"Bearer {user['token']}"}

    submit = client.post(
        "/api/v1/transactions/submit",
        headers=headers,
        json=transaction_payload(user["user_id"]),
    )
    listing = client.get("/api/v1/transactions/", headers=headers)

    assert submit.status_code == 200
    assert listing.status_code == 200
    assert all(item["user_id"] == user["user_id"] for item in listing.json()["transactions"])


def test_registered_user_cannot_submit_for_another_user_or_read_analyst_data():
    user = register_user("limited-user@example.com")
    headers = {"Authorization": f"Bearer {user['token']}"}

    submit = client.post(
        "/api/v1/transactions/submit",
        headers=headers,
        json=transaction_payload("demo-user"),
    )
    alerts = client.get("/api/v1/alerts/", headers=headers)
    analytics = client.get("/api/v1/analytics/dashboard", headers=headers)

    assert submit.status_code == 403
    assert alerts.status_code == 403
    assert analytics.status_code == 403


def test_registered_user_cannot_read_another_users_transaction():
    owner = register_user("transaction-owner@example.com")
    other_user = register_user("transaction-reader@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    reader_headers = {"Authorization": f"Bearer {other_user['token']}"}
    submitted = client.post(
        "/api/v1/transactions/submit",
        headers=owner_headers,
        json=transaction_payload(owner["user_id"]),
    )
    transaction_id = submitted.json()["transaction"]["transaction_id"]

    response = client.get(
        f"/api/v1/transactions/{transaction_id}",
        headers=reader_headers,
    )

    assert response.status_code == 403


def test_transaction_submission_rate_limit_returns_retry_after(monkeypatch):
    user = register_user("limited-submission@example.com")
    headers = {"Authorization": f"Bearer {user['token']}"}
    key = f"ratelimit:{user['user_id']}:transactions_submit"
    redis_service.reset(key)
    monkeypatch.setattr(transaction_routes.settings, "redis_rate_limit", 1)
    monkeypatch.setattr(transaction_routes.settings, "redis_rate_window_seconds", 30)

    first = client.post(
        "/api/v1/transactions/submit",
        headers=headers,
        json=transaction_payload(user["user_id"]),
    )
    limited = client.post(
        "/api/v1/transactions/submit",
        headers=headers,
        json=transaction_payload(user["user_id"]),
    )
    redis_service.reset(key)

    assert first.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "30"


def test_analyst_can_list_details_and_verify_transaction_integrity():
    analyst = {
        "_id": "test-integrity-analyst",
        "email": "integrity-analyst@example.com",
        "password_hash": hash_password("securepass"),
        "role": "analyst",
        "status": "active",
    }
    app.state.store["users"].append(analyst)
    headers = {"Authorization": f"Bearer {create_access_token(analyst['_id'])}"}
    user = register_user("integrity-user@example.com")
    user_headers = {"Authorization": f"Bearer {user['token']}"}
    submitted = client.post(
        "/api/v1/transactions/submit",
        headers=user_headers,
        json=transaction_payload(user["user_id"]),
    )
    transaction_id = submitted.json()["transaction"]["transaction_id"]

    listing = client.get("/api/v1/transactions/?limit=1", headers=headers)
    detail = client.get(f"/api/v1/transactions/{transaction_id}", headers=headers)
    verification = client.post(
        f"/api/v1/transactions/{transaction_id}/verify-integrity",
        headers=headers,
    )

    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert len(listing.json()["transactions"]) == 1
    assert detail.status_code == 200
    assert isinstance(detail.json()["transaction"]["device_id"], dict)
    assert verification.status_code == 200
    assert verification.json()["integrity_valid"] is True

    original_transaction = next(
        item for item in client.app.state.store["transactions"]
        if item["transaction_id"] == transaction_id
    )
    original_amount = original_transaction["amount"]
    original_transaction["amount"] = 9999
    tampered_verification = client.post(
        f"/api/v1/transactions/{transaction_id}/verify-integrity",
        headers=headers,
    )
    original_transaction["amount"] = original_amount

    assert tampered_verification.status_code == 200
    assert tampered_verification.json()["integrity_valid"] is False


def test_integrity_check_reads_authoritative_persisted_transaction(monkeypatch):
    analyst = {
        "_id": "test-persisted-integrity-analyst",
        "email": "persisted-integrity-analyst@example.com",
        "password_hash": hash_password("securepass"),
        "role": "analyst",
        "status": "active",
    }
    app.state.store["users"].append(analyst)
    headers = {"Authorization": f"Bearer {create_access_token(analyst['_id'])}"}
    user = register_user("persisted-integrity-user@example.com")
    submitted = client.post(
        "/api/v1/transactions/submit",
        headers={"Authorization": f"Bearer {user['token']}"},
        json=transaction_payload(user["user_id"]),
    )
    transaction = submitted.json()["transaction"]
    transaction["amount"] += 1

    async def read_tampered_record(collection_name, transaction_id):
        assert collection_name == "transactions"
        assert transaction_id == transaction["transaction_id"]
        return transaction

    monkeypatch.setattr(transaction_integrity, "mongo_connected", lambda: True)
    monkeypatch.setattr(transaction_integrity, "get_document", read_tampered_record)
    response = client.post(
        f"/api/v1/transactions/{transaction['transaction_id']}/verify-integrity",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["integrity_valid"] is False


def test_registration_cannot_assign_an_analyst_role():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "role-escalation@example.com", "password": "securepass", "role": "analyst"},
    )

    assert response.status_code == 422


def test_analyst_can_update_alert_review_status_and_invalid_status_is_rejected():
    analyst = {
        "_id": "test-alert-analyst",
        "email": "alert-analyst@example.com",
        "password_hash": hash_password("securepass"),
        "role": "analyst",
        "status": "active",
    }
    app.state.store["users"].append(analyst)
    headers = {"Authorization": f"Bearer {create_access_token(analyst['_id'])}"}
    alert_id = "test-review-alert"
    app.state.store["alerts"].append({
        "alert_id": alert_id,
        "transaction_id": "txn-test",
        "severity": "Medium",
        "reason": "Test review state",
        "status": "Open",
        "created_at": "2026-10-05T00:00:00+00:00",
        "updated_at": "2026-10-05T00:00:00+00:00",
    })

    review = client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers=headers,
        json={"status": "Under Investigation"},
    )
    invalid = client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers=headers,
        json={"status": "Escalated"},
    )

    assert review.status_code == 200
    assert review.json()["alert"]["status"] == "Under Investigation"
    assert invalid.status_code == 422


def test_login_and_registration_rate_limits_return_retry_after(monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "redis_rate_limit", 1)
    monkeypatch.setattr(auth_routes.settings, "redis_rate_window_seconds", 30)
    email = "rate-limited-login@example.com"
    identity = f"testclient\0{email}"
    login_key = f"ratelimit:auth_login:{hashlib.sha256(identity.encode()).hexdigest()}"
    registration_key = "ratelimit:testclient:auth_register"
    redis_service.reset(login_key)
    redis_service.reset(registration_key)

    first_login = client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpass"})
    limited_login = client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpass"})
    first_registration = client.post(
        "/api/v1/auth/register",
        json={"email": "rate-limit-one@example.com", "password": "securepass"},
    )
    limited_registration = client.post(
        "/api/v1/auth/register",
        json={"email": "rate-limit-two@example.com", "password": "securepass"},
    )

    redis_service.reset(login_key)
    redis_service.reset(registration_key)
    assert first_login.status_code == 401
    assert limited_login.status_code == 429
    assert limited_login.headers["retry-after"] == "30"
    assert first_registration.status_code == 200
    assert limited_registration.status_code == 429
