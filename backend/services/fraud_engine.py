from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .redis_service import redis_service

MODEL_PATH = Path(__file__).resolve().parents[2] / "ml" / "model.joblib"
_model: Any = None
_model_load_attempted = False


def _load_model() -> Any:
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    try:
        import joblib

        _model = joblib.load(MODEL_PATH)
    except Exception:
        _model = None
    return _model


def _model_risk(amount: float, velocity: int, device_events: int) -> int | None:
    """Return an ML-derived score when a trained model is available."""
    model = _load_model()
    if model is None:
        return None
    try:
        features = [[amount, datetime.now(timezone.utc).hour, velocity, device_events]]
        if hasattr(model, "predict_proba"):
            return int(round(float(model.predict_proba(features)[0][1]) * 100))
        if hasattr(model, "decision_function"):
            raw = float(model.decision_function(features)[0])
            return max(0, min(100, int(round(50 - raw * 15))))
    except Exception:
        return None
    return None


def score_transaction(payload: Dict[str, Any]) -> Dict[str, Any]:
    amount = float(payload.get("amount", 0))
    merchant = str(payload.get("merchant", "")).lower()
    currency = str(payload.get("currency", "USD")).upper()
    user_id = str(payload.get("user_id", "unknown"))
    device_id = str(payload.get("device_id", ""))
    risk_score = 10
    reasons: List[str] = []
    velocity = redis_service.velocity(user_id, window_seconds=3600)
    device_events = redis_service.device_activity(device_id)

    if amount >= 1500:
        risk_score += 25
        reasons.append("Large transaction value")
    if amount >= 5000:
        risk_score += 20
        reasons.append("Very large transaction volume")
    if merchant in {"crypto", "gambling", "adult"}:
        risk_score += 25
        reasons.append("High-risk merchant category")
    if currency not in {"USD", "EUR", "GBP"}:
        risk_score += 15
        reasons.append("Uncommon currency")
    if velocity >= 3:
        risk_score += 20
        reasons.append("High transaction velocity in the last hour")
    if device_events >= 10:
        risk_score += 15
        reasons.append("High device activity in the last 24 hours")
    if redis_service.is_suspicious_device(device_id):
        risk_score += 35
        reasons.append("Device is on the suspicious-device watchlist")

    model_score = _model_risk(amount, velocity, device_events)
    if model_score is None:
        reasons.append("ML model unavailable; rule-based fallback applied")
    elif model_score >= 50:
        risk_score = max(risk_score, model_score)
        reasons.append("ML anomaly model identified elevated risk")

    if risk_score >= 70:
        category = "High"
    elif risk_score >= 40:
        category = "Medium"
    else:
        category = "Low"

    return {
        "risk_score": min(risk_score, 100),
        "risk_category": category,
        "risk_reasons": reasons or ["No major risk indicators detected"],
    }
