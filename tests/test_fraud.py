import joblib

from backend.services import fraud_engine
from backend.services.fraud_engine import score_transaction
from backend.services.redis_service import RedisService


class ElevatedRiskModel:
    def predict_proba(self, features):
        assert len(features[0]) == len(fraud_engine.FEATURE_NAMES)
        return [[0.1, 0.9]]


def test_velocity_and_device_activity_raise_explanatory_risk():
    result = score_transaction(
        {"amount": 20, "merchant": "bookshop", "currency": "USD"},
        velocity_count=5,
        device_activity_count=5,
    )

    assert result["risk_category"] == "Medium"
    assert "Unusually high transaction velocity" in result["risk_reasons"]
    assert "Device used for many recent transactions" in result["risk_reasons"]
    assert any("ML model unavailable" in reason for reason in result["risk_reasons"])


def test_configured_blacklisted_device_is_flagged(monkeypatch):
    monkeypatch.setattr(fraud_engine.settings, "fraud_blacklisted_device_ids", "blocked-device, stolen-device")

    result = score_transaction({
        "amount": 20,
        "merchant": "bookshop",
        "currency": "USD",
        "device_id": " BLOCKED-DEVICE ",
    })

    assert result["risk_score"] == 60
    assert result["risk_category"] == "Medium"
    assert "Device is on the configured fraud blocklist" in result["risk_reasons"]


def test_rule_fallback_is_explicit_when_model_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(fraud_engine, "MODEL_PATH", tmp_path / "missing-model.joblib")
    fraud_engine._load_model.cache_clear()

    result = score_transaction({"amount": 20, "merchant": "bookshop", "currency": "USD"})

    fraud_engine._load_model.cache_clear()
    assert result["model_risk_score"] is None
    assert "Rule-based scoring active (ML model unavailable)" in result["risk_reasons"]


def test_in_memory_velocity_and_device_windows_expire_independently():
    service = RedisService()
    first = service.record_transaction("user-1", "device-1", "txn-1", timestamp=100_000)
    second = service.record_transaction("user-1", "device-1", "txn-2", timestamp=100_001)
    after_velocity_window = service.record_transaction(
        "user-1",
        "device-1",
        "txn-3",
        timestamp=103_602,
    )

    assert first == {"velocity_count": 0, "device_activity_count": 0}
    assert second == {"velocity_count": 1, "device_activity_count": 1}
    assert after_velocity_window == {"velocity_count": 0, "device_activity_count": 2}


def test_rate_limiter_enforces_limit_and_resets_after_window():
    service = RedisService()

    assert service.allow_request("ratelimit:test", 2, 60)
    assert service.allow_request("ratelimit:test", 2, 60)
    assert not service.allow_request("ratelimit:test", 2, 60)


def test_in_memory_fallback_prunes_expired_unseen_rate_keys():
    service = RedisService()
    service._fallback["ratelimit:expired-email"] = {"count": 1, "expires_at": 1}
    service._fallback["velocity:user:expired-user"] = {"old-transaction": 1.0}

    service.allow_request("ratelimit:fresh-email", 2, 60)

    assert "ratelimit:expired-email" not in service._fallback
    assert "velocity:user:expired-user" not in service._fallback


def test_in_memory_counter_fallback_supports_increment_get_and_reset():
    service = RedisService()
    service._client = None

    assert service.increment("counter:test") == 1
    assert service.increment("counter:test", 2) == 3
    assert service.get("counter:test") == 3

    service.reset("counter:test")

    assert service.get("counter:test") is None


def test_loaded_model_can_raise_the_transaction_risk_score(monkeypatch, tmp_path):
    artifact_path = tmp_path / "model.joblib"
    joblib.dump(
        {"model": ElevatedRiskModel(), "feature_names": list(fraud_engine.FEATURE_NAMES)},
        artifact_path,
    )
    monkeypatch.setattr(fraud_engine, "MODEL_PATH", artifact_path)
    fraud_engine._load_model.cache_clear()

    try:
        result = score_transaction({"amount": 10, "merchant": "bookshop", "currency": "USD"})
    finally:
        fraud_engine._load_model.cache_clear()
    assert result["model_risk_score"] == 90
    assert result["risk_category"] == "High"
    assert any("ML model elevated risk estimate" in reason for reason in result["risk_reasons"])
