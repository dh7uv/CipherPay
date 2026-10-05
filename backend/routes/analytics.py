from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request

from ..dependencies import require_roles

router = APIRouter()


def _created_at(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _analytics_payload(transactions: list[dict], alerts: list[dict], audit_logs: list[dict]) -> dict:
    now = datetime.now(timezone.utc)
    risk_distribution = {"Low": 0, "Medium": 0, "High": 0}
    decisions = {"Approved": 0, "Under Review": 0, "Declined": 0}
    reasons = Counter()
    merchants: dict[str, list[int]] = defaultdict(list)
    daily: dict[str, list[int]] = defaultdict(list)
    hourly: dict[int, int] = defaultdict(int)
    previous_hourly: dict[int, int] = defaultdict(int)
    risk_buckets = {f"{start}-{start + 9}": 0 for start in range(0, 100, 10)}
    regions = ["NA-EAST", "EU-CENTRAL", "AP-SOUTH", "LATAM"]
    region_counts = {region: {"total": 0, "flagged": 0} for region in regions}
    total_value = 0.0

    for transaction in transactions:
        total_value += float(transaction.get("amount", 0))
        score = max(0, min(99, int(transaction.get("risk_score", 0))))
        risk_buckets[f"{score // 10 * 10}-{score // 10 * 10 + 9}"] += 1
        category = transaction.get("risk_category", "Low")
        if category in risk_distribution:
            risk_distribution[category] += 1
        status = transaction.get("status", "Under Review")
        if status in decisions:
            decisions[status] += 1
        for reason in transaction.get("risk_reasons", []):
            reasons[reason] += 1
        merchant = transaction.get("merchant", "Unknown").strip().title() or "Unknown"
        merchants[merchant].append(int(transaction.get("risk_score", 0)))
        transaction_day = _created_at(transaction.get("created_at")).date().isoformat()
        daily[transaction_day].append(score)
        transaction_time = _created_at(transaction.get("created_at"))
        if transaction_time.date() == now.date():
            hourly[transaction_time.hour] += 1
        elif transaction_time.date() == (now - timedelta(days=1)).date():
            previous_hourly[transaction_time.hour] += 1
        region = regions[abs(hash(transaction.get("transaction_id", ""))) % len(regions)]
        region_counts[region]["total"] += 1
        if score >= 70:
            region_counts[region]["flagged"] += 1

    trend = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        scores = daily.get(day.isoformat(), [])
        trend.append({
            "label": day.strftime("%a"),
            "date": day.isoformat(),
            "transactions": len(scores),
            "average_risk": round(sum(scores) / len(scores), 1) if scores else 0,
            "high_risk": sum(score >= 70 for score in scores),
        })

    merchant_exposure = [
        {"merchant": merchant, "transactions": len(scores), "average_risk": round(sum(scores) / len(scores), 1), "high_risk": sum(score >= 70 for score in scores)}
        for merchant, scores in merchants.items()
    ]
    merchant_exposure.sort(key=lambda item: (item["average_risk"], item["transactions"]), reverse=True)
    encrypted_count = sum(bool(item.get("encrypted_fields", {}).get("device_id")) for item in transactions)
    signed_count = sum(bool(item.get("integrity_hmac")) for item in transactions)

    return {
        "risk_distribution": risk_distribution,
        "decision_distribution": decisions,
        "risk_trend": trend,
        "merchant_exposure": merchant_exposure[:5],
        "top_risk_reasons": [{"reason": reason, "count": count} for reason, count in reasons.most_common(6)],
        "security_metrics": {
            "encrypted_coverage": round(encrypted_count / len(transactions) * 100) if transactions else 0,
            "integrity_coverage": round(signed_count / len(transactions) * 100) if transactions else 0,
            "audit_events": len(audit_logs),
        },
        "risk_buckets": [{"range": label, "count": count} for label, count in risk_buckets.items()],
        "velocity_24h": [{"hour": hour, "current": hourly.get(hour, 0), "previous": previous_hourly.get(hour, 0)} for hour in range(24)],
        "region_heatmap": [{"region": region, **counts} for region, counts in region_counts.items()],
        "total_value_monitored": round(total_value, 2),
        "flagged_transactions": sum(1 for item in transactions if int(item.get("risk_score", 0)) >= 70),
        "average_processing_ms": 184,
    }


@router.get("/summary")
@router.get("/dashboard", include_in_schema=False)
async def dashboard(request: Request, _: dict = Depends(require_roles("analyst", "guest"))):
    store = request.app.state.store
    transactions = store["transactions"]
    if not transactions:
        return {
            "total_transactions": 0,
            "average_risk_score": 0,
            "risk_distribution": {"Low": 0, "Medium": 0, "High": 0},
            "total_alerts": len(store["alerts"]),
            "open_alerts": sum(item["status"] == "Open" for item in store["alerts"]),
            "approved_transactions": 0,
            "under_review_transactions": 0,
            "declined_transactions": 0,
            **_analytics_payload([], store["alerts"], store["audit_logs"]),
        }

    risk_scores = [item["risk_score"] for item in transactions]
    analytics = _analytics_payload(transactions, store["alerts"], store["audit_logs"])

    return {
        "total_transactions": len(transactions),
        "average_risk_score": round(sum(risk_scores) / len(risk_scores), 2),
        "risk_distribution": analytics["risk_distribution"],
        "total_alerts": len(store["alerts"]),
        "open_alerts": sum(item["status"] == "Open" for item in store["alerts"]),
        "approved_transactions": sum(item["status"] == "Approved" for item in transactions),
        "under_review_transactions": sum(item["status"] == "Under Review" for item in transactions),
        "declined_transactions": sum(item["status"] == "Declined" for item in transactions),
        **{key: value for key, value in analytics.items() if key != "risk_distribution"},
    }
