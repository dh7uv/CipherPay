from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import get_current_user
from ..services.attack_simulator import ScenarioId, list_scenarios, run_attack_simulation

router = APIRouter()


class SimulationRequest(BaseModel):
    scenario_id: ScenarioId


@router.get("/scenarios")
async def get_scenarios(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    if current_user["role"] != "analyst":
        raise HTTPException(status_code=403, detail="Analyst access required")
    return {"scenarios": list_scenarios()}


@router.post("/run")
async def run_scenario(
    payload: SimulationRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    if current_user["role"] != "analyst":
        raise HTTPException(status_code=403, detail="Analyst access required")
    return run_attack_simulation(payload.scenario_id)
