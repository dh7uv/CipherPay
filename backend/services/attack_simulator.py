from __future__ import annotations

from typing import Any, Literal

from .fraud_engine import score_transaction

ScenarioId = Literal[
    "card_testing",
    "account_takeover",
    "velocity_abuse",
    "device_reuse",
    "normal_baseline",
]

_SCENARIOS: dict[str, dict[str, Any]] = {
    "card_testing": {
        "name": "Card testing pattern",
        "description": "A burst of low-value attempts from one synthetic account and device.",
        "pattern": "Repeated low-value attempts",
        "transactions": [
            {
                "amount": float(amount),
                "currency": "USD",
                "merchant": "bookshop",
                "user_id": "sim-user-card-testing",
                "device_id": "sim-device-card-testing",
                "velocity_count": index,
                "device_activity_count": index,
            }
            for index, amount in enumerate((1, 2, 3, 4, 5, 6))
        ],
    },
    "account_takeover": {
        "name": "Account takeover-like purchase",
        "description": "A sudden high-value purchase combines a high-risk merchant and uncommon currency.",
        "pattern": "High-value purchase with elevated merchant and currency signals",
        "transactions": [
            {
                "amount": 6000.0,
                "currency": "JPY",
                "merchant": "crypto",
                "user_id": "sim-user-account-takeover",
                "device_id": "sim-new-device-account-takeover",
                "velocity_count": 0,
                "device_activity_count": 0,
            }
        ],
    },
    "velocity_abuse": {
        "name": "Transaction velocity burst",
        "description": "Repeated medium-value purchases arrive rapidly from one synthetic account.",
        "pattern": "Rapid repeated purchases",
        "transactions": [
            {
                "amount": 250.0,
                "currency": "USD",
                "merchant": "bookshop",
                "user_id": "sim-user-velocity",
                "device_id": "sim-device-velocity",
                "velocity_count": index,
                "device_activity_count": index,
            }
            for index in range(6)
        ],
    },
    "device_reuse": {
        "name": "Shared device across accounts",
        "description": "Distinct synthetic accounts reuse one device while using an uncommon currency.",
        "pattern": "Device reuse across synthetic accounts",
        "transactions": [
            {
                "amount": 100.0,
                "currency": "JPY",
                "merchant": "bookshop",
                "user_id": f"sim-user-device-reuse-{index + 1}",
                "device_id": "sim-shared-device",
                "velocity_count": 0,
                "device_activity_count": index,
            }
            for index in range(6)
        ],
    },
    "normal_baseline": {
        "name": "Normal transaction control",
        "description": "A single ordinary purchase used to compare detection against normal activity.",
        "pattern": "Ordinary low-value purchase",
        "transactions": [
            {
                "amount": 45.0,
                "currency": "USD",
                "merchant": "bookshop",
                "user_id": "sim-user-normal-control",
                "device_id": "sim-device-normal-control",
                "velocity_count": 0,
                "device_activity_count": 0,
            }
        ],
    },
}


def list_scenarios() -> list[dict[str, str]]:
    return [
        {
            "id": scenario_id,
            "name": str(scenario["name"]),
            "description": str(scenario["description"]),
        }
        for scenario_id, scenario in _SCENARIOS.items()
    ]


def run_attack_simulation(scenario_id: ScenarioId) -> dict[str, Any]:
    scenario = _SCENARIOS[scenario_id]
    results: list[dict[str, Any]] = []

    for index, payload in enumerate(scenario["transactions"], start=1):
        risk = score_transaction(
            payload,
            velocity_count=payload["velocity_count"],
            device_activity_count=payload["device_activity_count"],
        )
        detected = risk["risk_category"] in {"Medium", "High"}
        results.append(
            {
                "simulation_id": f"SIM-{scenario_id.upper()}-{index:02d}",
                "amount": payload["amount"],
                "currency": payload["currency"],
                "merchant": payload["merchant"],
                "risk_score": risk["risk_score"],
                "risk_category": risk["risk_category"],
                "risk_reasons": risk["risk_reasons"],
                "detected": detected,
                "scenario_signal": str(scenario["pattern"]),
            }
        )

    alerts = [
        {
            "simulation_id": result["simulation_id"],
            "severity": result["risk_category"],
            "reason": "; ".join(result["risk_reasons"]),
        }
        for result in results
        if result["detected"]
    ]
    return {
        "scenario": {
            "id": scenario_id,
            "name": scenario["name"],
            "description": scenario["description"],
        },
        "simulation_only": True,
        "transactions": results,
        "alerts": alerts,
        "summary": {
            "transaction_count": len(results),
            "detected_count": len(alerts),
            "highest_risk_score": max(result["risk_score"] for result in results),
        },
    }
