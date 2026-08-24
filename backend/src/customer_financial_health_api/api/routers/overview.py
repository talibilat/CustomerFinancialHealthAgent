from datetime import datetime, timezone
from decimal import Decimal
import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db, get_guidance_generator
from customer_financial_health_api.api.schemas import (
    DifficultyOut,
    MoneyEntryOut,
    OverviewResponse,
    PersonalizedExplanationOut,
    PersonalizedExplanationRequest,
    ResilienceOut,
    SupportRouteOut,
)
from customer_financial_health_api.domain.classification import OutgoingTreatment
from customer_financial_health_api.domain.difficulty import assess_financial_difficulty
from customer_financial_health_api.domain.financial_health import (
    MonthlyPositionResult,
    ResilienceResult,
)
from customer_financial_health_api.domain.guidance import (
    GuidanceFacts,
    GuidanceGenerator,
    create_personalized_explanation,
    deterministic_explanation,
)
from customer_financial_health_api.persistence.repository import (
    ConfirmedSnapshotView,
    IdempotencyConflict,
    get_demo_customer,
    get_effective_snapshot,
    get_latest_personalized_explanation,
    record_personalized_explanation,
)

router = APIRouter()


def _entries_out(entries) -> list[MoneyEntryOut]:
    return [
        MoneyEntryOut(
            original_amount=str(entry.original_amount),
            original_frequency=entry.original_frequency.value,
            normalized_monthly_amount=str(entry.normalized_monthly_amount),
        )
        for entry in entries
    ]


def _optional_str(amount) -> str | None:
    return str(amount) if amount is not None else None


def _resilience_out(resilience: ResilienceResult) -> ResilienceOut:
    return ResilienceOut(
        accessible_savings=_optional_str(resilience.accessible_savings),
        protected_reserve=_optional_str(resilience.protected_reserve),
        current_account_balance=_optional_str(resilience.current_account_balance),
        known_arrears=_optional_str(resilience.known_arrears),
        savings_above_reserve=_optional_str(resilience.savings_above_reserve),
        reserve_gap=_optional_str(resilience.reserve_gap),
        result_code=resilience.result_code.value if resilience.result_code else None,
        warnings=list(resilience.warnings),
    )


def _facts(snapshot: ConfirmedSnapshotView, difficulty) -> GuidanceFacts:
    warnings = tuple(dict.fromkeys((*snapshot.warnings, *difficulty.warnings)))
    return GuidanceFacts(
        normalized_monthly_income=snapshot.normalized_monthly_income,
        normalized_monthly_outgoings=snapshot.normalized_monthly_outgoings,
        monthly_headroom=snapshot.monthly_headroom,
        result_code=snapshot.result_code.value,
        warning_codes=warnings,
        support_codes=tuple(route.code.value for route in difficulty.support_routes),
        resilience={
            "accessible_savings": _optional_str(snapshot.resilience.accessible_savings),
            "protected_reserve": _optional_str(snapshot.resilience.protected_reserve),
            "savings_above_reserve": _optional_str(snapshot.resilience.savings_above_reserve),
            "reserve_gap": _optional_str(snapshot.resilience.reserve_gap),
            "result_code": (
                snapshot.resilience.result_code.value
                if snapshot.resilience.result_code
                else None
            ),
        },
    )


def _personalized_out(stored) -> PersonalizedExplanationOut:
    return PersonalizedExplanationOut(
        snapshot_id=stored.snapshot_id,
        text=stored.text,
        outcome=stored.outcome.value,
        deployment=stored.deployment,
        prompt_version=stored.prompt_version,
        schema_version=stored.schema_version,
        created_at=stored.created_at,
    )


def _to_response(session: Session, customer_id, snapshot: ConfirmedSnapshotView) -> OverviewResponse:
    protected = sum(
        (
            entry.normalized_monthly_amount
            for entry in snapshot.outgoing_entries
            if entry.outgoing_treatment is OutgoingTreatment.PROTECTED_OUTGOING
        ),
        start=Decimal("0.00"),
    )
    difficulty = assess_financial_difficulty(
        MonthlyPositionResult(
            calculation_policy_version=snapshot.calculation_policy_version,
            normalized_monthly_income=snapshot.normalized_monthly_income,
            normalized_monthly_outgoings=snapshot.normalized_monthly_outgoings,
            monthly_headroom=snapshot.monthly_headroom,
            result_code=snapshot.result_code,
            warnings=snapshot.warnings,
        ),
        protected,
    )
    facts = _facts(snapshot, difficulty)
    personalized = get_latest_personalized_explanation(
        session, customer_id=customer_id, snapshot_id=snapshot.id
    )
    return OverviewResponse(
        customer_id=str(customer_id),
        snapshot_id=snapshot.id,
        statement_period=snapshot.statement_period,
        confirmed_at=snapshot.confirmed_at,
        calculation_policy_version=snapshot.calculation_policy_version,
        normalized_monthly_income=str(snapshot.normalized_monthly_income),
        normalized_monthly_outgoings=str(snapshot.normalized_monthly_outgoings),
        monthly_headroom=str(snapshot.monthly_headroom),
        result_code=snapshot.result_code.value,
        warnings=list(snapshot.warnings),
        income_entries=_entries_out(snapshot.income_entries),
        outgoing_entries=_entries_out(snapshot.outgoing_entries),
        resilience=_resilience_out(snapshot.resilience),
        difficulty=DifficultyOut(
            result_code=difficulty.result_code.value,
            title=difficulty.title,
            explanation=difficulty.explanation,
            shortfall=_optional_str(difficulty.shortfall),
            protected_monthly_outgoings=str(difficulty.protected_monthly_outgoings),
            warnings=list(difficulty.warnings),
            support_routes=[
                SupportRouteOut(
                    code=route.code.value,
                    label=route.label,
                    description=route.description,
                    url=route.url,
                    external=route.external,
                )
                for route in difficulty.support_routes
            ],
        ),
        deterministic_explanation=deterministic_explanation(facts),
        personalized_explanation=(
            _personalized_out(personalized) if personalized is not None else None
        ),
    )


@router.get("/overview", response_model=OverviewResponse)
def get_overview(session: Session = Depends(get_db)) -> OverviewResponse:
    customer = get_demo_customer(session)
    if customer is None:
        raise HTTPException(status_code=404, detail="no_customer_data")

    snapshot = get_effective_snapshot(session, customer_id=customer.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="no_confirmed_snapshot")

    return _to_response(session, customer.id, snapshot)


@router.post(
    "/overview/personalized-explanation",
    response_model=PersonalizedExplanationOut,
)
def request_personalized_explanation(
    request: PersonalizedExplanationRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    session: Session = Depends(get_db),
    generator: GuidanceGenerator | None = Depends(get_guidance_generator),
) -> PersonalizedExplanationOut:
    customer = get_demo_customer(session)
    if customer is None:
        raise HTTPException(status_code=404, detail="no_customer_data")
    customer_id = customer.id
    snapshot = get_effective_snapshot(session, customer_id=customer_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="no_confirmed_snapshot")
    if snapshot.id != request.snapshot_id:
        raise HTTPException(status_code=409, detail="snapshot_no_longer_effective")

    protected = sum(
        (
            entry.normalized_monthly_amount
            for entry in snapshot.outgoing_entries
            if entry.outgoing_treatment is OutgoingTreatment.PROTECTED_OUTGOING
        ),
        start=Decimal("0.00"),
    )
    difficulty = assess_financial_difficulty(
        MonthlyPositionResult(
            calculation_policy_version=snapshot.calculation_policy_version,
            normalized_monthly_income=snapshot.normalized_monthly_income,
            normalized_monthly_outgoings=snapshot.normalized_monthly_outgoings,
            monthly_headroom=snapshot.monthly_headroom,
            result_code=snapshot.result_code,
            warnings=snapshot.warnings,
        ),
        protected,
    )
    facts = _facts(snapshot, difficulty)
    session.rollback()
    explanation = create_personalized_explanation(facts, generator)
    current_snapshot = get_effective_snapshot(session, customer_id=customer_id)
    if current_snapshot is None or current_snapshot.id != request.snapshot_id:
        session.rollback()
        raise HTTPException(status_code=409, detail="snapshot_no_longer_effective")
    fingerprint = hashlib.sha256(str(request.snapshot_id).encode()).hexdigest()
    try:
        stored = record_personalized_explanation(
            session,
            customer_id=customer_id,
            snapshot_id=request.snapshot_id,
            explanation=explanation,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            created_at=datetime.now(timezone.utc),
        )
        session.commit()
    except IdempotencyConflict as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="idempotency_key_conflict") from error
    return _personalized_out(stored)
