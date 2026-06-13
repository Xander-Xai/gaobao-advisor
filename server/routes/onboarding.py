"""Onboarding wizard endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

from server.services.slot_extractor import SlotExtractor

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])
_slot_extractor = SlotExtractor()

STEPS = {
    1: {"required": ["province"], "next": 2},
    2: {"required": ["score"], "next": 3},
    3: {"required": ["subject", "interest"], "next": None},
}


class OnboardingRequest(BaseModel):
    step: int
    data: dict


@router.post("")
async def onboarding_step(request: OnboardingRequest):
    step_config = STEPS.get(request.step)
    if not step_config:
        return {"error": "无效的步骤"}
    slots = _slot_extractor.extract(str(request.data))
    missing = [f for f in step_config["required"] if not slots.get(f)]
    return {
        "step": request.step,
        "extracted": {k: v for k, v in slots.items() if v},
        "missing": missing,
        "next_step": step_config["next"],
        "message": "信息已记录" if not missing else f"请补充：{', '.join(missing)}",
    }
