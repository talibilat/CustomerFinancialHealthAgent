"""Explicitly demo-only selection of controlled fictional states."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db
from customer_financial_health_api.api.schemas import (
    DemoPresetListResponse,
    DemoPresetOut,
    DemoResetRequest,
    DemoResetResponse,
)
from customer_financial_health_api.persistence.demo_presets import (
    DEMO_PRESETS,
    PRESET_CODES,
    activate_demo_preset,
)
from customer_financial_health_api.settings import Settings, get_settings

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/presets", response_model=DemoPresetListResponse)
def list_demo_presets(
    settings: Settings = Depends(get_settings),
) -> DemoPresetListResponse:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="not_found")
    return DemoPresetListResponse(
        presets=[
            DemoPresetOut(
                code=preset.code,
                label=preset.label,
                description=preset.description,
            )
            for preset in DEMO_PRESETS
        ]
    )


@router.post("/reset", response_model=DemoResetResponse)
def reset_demo(
    request: DemoResetRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DemoResetResponse:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="not_found")
    if not request.confirmed_reset:
        raise HTTPException(status_code=400, detail="demo_reset_confirmation_required")
    if request.preset not in PRESET_CODES:
        raise HTTPException(status_code=422, detail="demo_preset_not_supported")

    with session.begin():
        activate_demo_preset(session, request.preset)

    return DemoResetResponse(
        preset=request.preset,
        message="Fictional demo data loaded.",
    )
