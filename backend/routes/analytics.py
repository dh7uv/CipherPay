from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..dependencies import require_analyst

router = APIRouter()


@router.get("/dashboard")
async def dashboard(request: Request, _: dict = Depends(require_analyst)):
    store = request.app.state.store
    transactions = store["transactions"]
    if not transactions:
        return {
            "total_transactions": 0,
            "average_risk_score": 0,
            "risk_distribution": {"Low": 0, "Medium": 0, "High": 0},
            "total_alerts": len(store["alerts"]),
        }

    risk_scores = [item["risk_score"] for item in transactions]
    risk_distribution = {"Low": 0, "Medium": 0, "High": 0}
    for item in transactions:
        category = item["risk_category"]
        if category in risk_distribution:
            risk_distribution[category] += 1

    return {
        "total_transactions": len(transactions),
        "average_risk_score": round(sum(risk_scores) / len(risk_scores), 2),
        "risk_distribution": risk_distribution,
        "total_alerts": len(store["alerts"]),
    }
