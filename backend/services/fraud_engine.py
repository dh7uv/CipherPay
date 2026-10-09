from __future__ import annotations

import logging
import pickle
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import joblib

from ..config import get_settings
from .fraud_features import FEATURE_NAMES, normalize_features

logger = logging.getLogger(__name__)
settings = get_settings()
MODEL_PATH = Path(__file__).resolve().parents[2] / "ml" / "model.joblib"


@lru_cache(maxsize=1)
def _load_model():
    if not MODEL_PATH.is_file():
        return None

    try:
        artifact = joblib.load(MODEL_PATH)
    except (OSError, EOFError, ImportError, ValueError, AttributeError, pickle.UnpicklingError) as error:
        logger.warning("Fraud model could not be loaded; using rule-based scoring: %s", error)
        return None

    if not isinstance(artifact, dict):
        logger.warning("Fraud model artifact has an invalid structure; using rule-based scoring")
        return None

    feature_names = artifact.get("feature_names")
    if not isinstance(feature_names, (list, tuple)):
        logger.warning("Fraud model artifact has an invalid feature schema; using rule-based scoring")
        return None
    model = artifact.get("model")
    if tuple(feature_names) != FEATURE_NAMES or not callable(getattr(model, "predict_proba", None)):
        logger.warning("Fraud model artifact is incompatible; using rule-based scoring")
        return None
    return model


def score_transaction(
    payload: Dict[str, Any],
    velocity_count: int = 0,
    device_activity_count: int = 0,
) -> Dict[str, Any]:
    amount = float(payload.get("amount", 0))
    merchant_category = payload.get("merchant_category")
    merchant = str(merchant_category or payload.get("merchant", "")).strip().casefold()
    currency = str(payload.get("currency", "USD")).upper()
    device_id = str(payload.get("device_id", "")).strip().casefold()
    blacklisted_devices = {
        device.strip().casefold()
        for device in settings.fraud_blacklisted_device_ids.split(",")
        if device.strip()
    }
    risk_score = 10
    reasons: List[str] = []

    if amount >= 1500:
        risk_score += 25
        reasons.append("Large transaction value")
    if amount >= 5000:
        risk_score += 20
        reasons.append("Very large transaction volume")
    if merchant in {"crypto", "cryptocurrency", "gambling", "adult"}:
        risk_score += 25
        reasons.append("High-risk merchant category")
    if currency not in {"USD", "EUR", "GBP"}:
        risk_score += 15
        reasons.append("Uncommon currency")
    if velocity_count >= 5:
        risk_score += 20
        reasons.append("Unusually high transaction velocity")
    if device_activity_count >= 5:
        risk_score += 15
        reasons.append("Device used for many recent transactions")
    if device_id and device_id in blacklisted_devices:
        risk_score += 50
        reasons.append("Device is on the configured fraud blocklist")

    model = _load_model()
    model_score = None
    if model is None:
        reasons.append("Rule-based scoring active (ML model unavailable)")
    else:
        features = [normalize_features(
            amount,
            datetime.now(timezone.utc).hour,
            velocity_count,
            device_activity_count,
        )]
        model_score = round(float(model.predict_proba(features)[0][1]) * 100)
        if model_score >= 30:
            reasons.append(f"ML model elevated risk estimate ({model_score}/100)")
        risk_score = max(risk_score, model_score)

    if not reasons:
        reasons.append("No major risk indicators detected")

    if risk_score >= 70:
        category = "High"
    elif risk_score >= 40:
        category = "Medium"
    else:
        category = "Low"

    return {
        "risk_score": min(risk_score, 100),
        "risk_category": category,
        "risk_reasons": reasons,
        "model_risk_score": model_score,
    }
