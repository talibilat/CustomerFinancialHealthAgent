from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db
from customer_financial_health_api.api.schemas import (
    DifficultyOut,
    MoneyEntryOut,
    OverviewResponse,
    ResilienceOut,
    SupportRouteOut,
)
from customer_financial_health_api.domain.classification import OutgoingTreatment
from customer_financial_health_api.domain.difficulty import assess_financial_difficulty
from customer_financial_health_api.domain.financial_health import (
    MonthlyPositionResult,
    ResilienceResult,
)
from customer_financial_health_api.persistence.repository import (
    ConfirmedSnapshotView,
    get_demo_customer,
    get_effective_snapshot,
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


def _to_response(customer_id, snapshot: ConfirmedSnapshotView) -> OverviewResponse:
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
    return OverviewResponse(
        customer_id=str(customer_id),
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
    )


@router.get("/overview", response_model=OverviewResponse)
def get_overview(session: Session = Depends(get_db)) -> OverviewResponse:
    customer = get_demo_customer(session)
    if customer is None:
        raise HTTPException(status_code=404, detail="no_customer_data")

    snapshot = get_effective_snapshot(session, customer_id=customer.id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="no_confirmed_snapshot")

    return _to_response(customer.id, snapshot)
