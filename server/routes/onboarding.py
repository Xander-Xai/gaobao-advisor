"""Onboarding wizard endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

from slots.extractor import SlotExtractor

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])
_slot_extractor = SlotExtractor()

STEPS = {
    1: {"required": ["province"], "next": 2},
    2: {"required": ["score_rank"], "next": 3},
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

    # Extract values directly from the submitted dict
    simple_slots = {}
    for k, v in request.data.items():
        if v is not None and str(v).strip():
            simple_slots[k] = str(v).strip()

    # Also run extractor on concatenated values for additional slot detection
    text = " ".join(str(v) for v in request.data.values() if v)
    if text:
        slots_dict, _ = _slot_extractor.extract(text)
        for k, v in slots_dict.items():
            if v.get("filled") and k not in simple_slots:
                simple_slots[k] = v["value"]

    missing = [f for f in step_config["required"] if not simple_slots.get(f)]
    return {
        "step": request.step,
        "extracted": simple_slots,
        "missing": missing,
        "next_step": step_config["next"],
        "message": "信息已记录" if not missing else f"请补充：{', '.join(missing)}",
    }
