import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import fraud_engine
from backend.services.auth_service import create_access_token

client = TestClient(app)

SCENARIOS = (
    ("card_testing", "Unusually high transaction velocity", 1),
    ("velocity_abuse", "Unusually high transaction velocity", 1),
    ("device_reuse", "Device used for many recent transactions", 1),
    ("account_takeover", "High-risk merchant category", 1),
)


def analyst_headers() -> dict[str, str]:
    analyst = {
        "_id": "simulation-analyst",
        "email": "simulation-analyst@example.com",
        "role": "analyst",
        "status": "active",
    }
    app.state.store["users"].append(analyst)
    return {"Authorization": f"Bearer {create_access_token(analyst['_id'])}"}


@pytest.mark.parametrize(("scenario_id", "expected_reason", "expected_detections"), SCENARIOS)
def test_attack_simulations_use_fraud_rules_without_persisting_data(
    scenario_id,
    expected_reason,
    expected_detections,
    monkeypatch,
):
    monkeypatch.setattr(fraud_engine, "_load_model", lambda: None)
    headers = analyst_headers()
    before = {name: len(items) for name, items in app.state.store.items()}

    response = client.post(
        "/api/v1/simulations/run",
        headers=headers,
        json={"scenario_id": scenario_id},
    )
    result = response.json()

    assert response.status_code == 200
    assert result["simulation_only"] is True
    assert result["summary"]["detected_count"] == expected_detections
    assert result["transactions"][-1]["detected"] is True
    assert any(expected_reason in reason for reason in result["transactions"][-1]["risk_reasons"])
    assert len(app.state.store["transactions"]) == before["transactions"]
    assert len(app.state.store["alerts"]) == before["alerts"]
    assert len(app.state.store["audit_logs"]) == before["audit_logs"]
    assert len(result["alerts"]) == expected_detections


def test_analyst_can_list_synthetic_scenarios():
    result = client.get(
        "/api/v1/simulations/scenarios",
        headers=analyst_headers(),
    )

    assert result.status_code == 200
    assert {scenario["id"] for scenario in result.json()["scenarios"]} == {
        "card_testing",
        "account_takeover",
        "velocity_abuse",
        "device_reuse",
        "normal_baseline",
    }


def test_normal_control_is_not_flagged(monkeypatch):
    monkeypatch.setattr(fraud_engine, "_load_model", lambda: None)

    response = client.post(
        "/api/v1/simulations/run",
        headers=analyst_headers(),
        json={"scenario_id": "normal_baseline"},
    )

    result = response.json()
    assert response.status_code == 200
    assert result["summary"]["detected_count"] == 0
    assert result["transactions"][0]["risk_category"] == "Low"
    assert result["alerts"] == []


def test_simulation_scenarios_are_analyst_only():
    user = {
        "_id": "simulation-user",
        "email": "simulation-user@example.com",
        "role": "user",
        "status": "active",
    }
    app.state.store["users"].append(user)
    headers = {"Authorization": f"Bearer {create_access_token(user['_id'])}"}

    catalog = client.get("/api/v1/simulations/scenarios", headers=headers)
    run = client.post(
        "/api/v1/simulations/run",
        headers=headers,
        json={"scenario_id": "card_testing"},
    )

    assert catalog.status_code == 403
    assert run.status_code == 403


def test_unknown_simulation_scenario_is_rejected():
    response = client.post(
        "/api/v1/simulations/run",
        headers=analyst_headers(),
        json={"scenario_id": "unknown"},
    )

    assert response.status_code == 422
