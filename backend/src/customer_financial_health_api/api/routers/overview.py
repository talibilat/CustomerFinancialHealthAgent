from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db
from customer_financial_health_api.api.schemas import MoneyEntryOut, OverviewResponse
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


def _to_response(customer_id, snapshot: ConfirmedSnapshotView) -> OverviewResponse:
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
