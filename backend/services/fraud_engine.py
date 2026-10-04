from __future__ import annotations

from typing import Any, Dict, List


def score_transaction(payload: Dict[str, Any]) -> Dict[str, Any]:
    amount = float(payload.get("amount", 0))
    merchant = str(payload.get("merchant", "")).lower()
    currency = str(payload.get("currency", "USD")).upper()
    risk_score = 10
    reasons: List[str] = []

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
