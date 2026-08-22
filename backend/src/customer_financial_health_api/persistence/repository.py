import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_financial_health_api.domain.financial_health import (
    CurrentPositionResultCode,
    Frequency,
    MoneyEntry,
    MonthlyPositionResult,
    ResilienceResult,
    ResilienceResultCode,
    normalize_to_monthly,
)
from customer_financial_health_api.persistence.models import (
    ConfirmedSnapshot,
    Customer,
    SnapshotIncomeEntry,
    SnapshotOutgoingEntry,
)


@dataclass(frozen=True)
class SnapshotEntryView:
    original_amount: Decimal
    original_frequency: Frequency
    normalized_monthly_amount: Decimal


@dataclass(frozen=True)
class ConfirmedSnapshotView:
    id: uuid.UUID
    customer_id: uuid.UUID
    statement_period: date
    confirmed_at: datetime
    calculation_policy_version: str
    normalized_monthly_income: Decimal
    normalized_monthly_outgoings: Decimal
    monthly_headroom: Decimal
    result_code: CurrentPositionResultCode
    warnings: tuple[str, ...]
    income_entries: tuple[SnapshotEntryView, ...]
    outgoing_entries: tuple[SnapshotEntryView, ...]
    resilience: ResilienceResult


def create_customer(session: Session) -> Customer:
    customer = Customer()
    session.add(customer)
    session.flush()
    return customer


def get_demo_customer(session: Session) -> Customer | None:
    stmt = select(Customer).order_by(Customer.created_at).limit(1)
    return session.execute(stmt).scalar_one_or_none()


def _entry_rows(entries: Sequence[MoneyEntry], position_amounts: Sequence[Decimal], row_type):
    return [
        row_type(
            original_amount=entry.amount,
            original_frequency=entry.frequency.value,
            normalized_monthly_amount=normalized_amount,
            sort_order=index,
        )
        for index, (entry, normalized_amount) in enumerate(zip(entries, position_amounts))
    ]


def save_confirmed_snapshot(
    session: Session,
    *,
    customer_id: uuid.UUID,
    statement_period: date,
    confirmed_at: datetime,
    position: MonthlyPositionResult,
    income_entries: Sequence[MoneyEntry],
    outgoing_entries: Sequence[MoneyEntry],
    resilience: ResilienceResult,
    supersedes_snapshot_id: uuid.UUID | None = None,
) -> ConfirmedSnapshot:
    income_normalized = [normalize_to_monthly(e.amount, e.frequency) for e in income_entries]
    outgoing_normalized = [normalize_to_monthly(e.amount, e.frequency) for e in outgoing_entries]

    snapshot = ConfirmedSnapshot(
        customer_id=customer_id,
        statement_period=statement_period,
        confirmed_at=confirmed_at,
        calculation_policy_version=position.calculation_policy_version,
        normalized_monthly_income=position.normalized_monthly_income,
        normalized_monthly_outgoings=position.normalized_monthly_outgoings,
        monthly_headroom=position.monthly_headroom,
        result_code=position.result_code.value,
        warnings=list(position.warnings),
        supersedes_snapshot_id=supersedes_snapshot_id,
        income_entries=_entry_rows(income_entries, income_normalized, SnapshotIncomeEntry),
        outgoing_entries=_entry_rows(outgoing_entries, outgoing_normalized, SnapshotOutgoingEntry),
        current_account_balance=resilience.current_account_balance,
        accessible_savings=resilience.accessible_savings,
        protected_reserve=resilience.protected_reserve,
        known_arrears=resilience.known_arrears,
        savings_above_reserve=resilience.savings_above_reserve,
        reserve_gap=resilience.reserve_gap,
        resilience_result_code=resilience.result_code.value if resilience.result_code else None,
        resilience_warnings=list(resilience.warnings),
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def _to_view(snapshot: ConfirmedSnapshot) -> ConfirmedSnapshotView:
    return ConfirmedSnapshotView(
        id=snapshot.id,
        customer_id=snapshot.customer_id,
        statement_period=snapshot.statement_period,
        confirmed_at=snapshot.confirmed_at,
        calculation_policy_version=snapshot.calculation_policy_version,
        normalized_monthly_income=snapshot.normalized_monthly_income,
        normalized_monthly_outgoings=snapshot.normalized_monthly_outgoings,
        monthly_headroom=snapshot.monthly_headroom,
        result_code=CurrentPositionResultCode(snapshot.result_code),
        warnings=tuple(snapshot.warnings),
        income_entries=tuple(
            SnapshotEntryView(
                original_amount=e.original_amount,
                original_frequency=Frequency(e.original_frequency),
                normalized_monthly_amount=e.normalized_monthly_amount,
            )
            for e in snapshot.income_entries
        ),
        outgoing_entries=tuple(
            SnapshotEntryView(
                original_amount=e.original_amount,
                original_frequency=Frequency(e.original_frequency),
                normalized_monthly_amount=e.normalized_monthly_amount,
            )
            for e in snapshot.outgoing_entries
        ),
        resilience=ResilienceResult(
            accessible_savings=snapshot.accessible_savings,
            protected_reserve=snapshot.protected_reserve,
            current_account_balance=snapshot.current_account_balance,
            known_arrears=snapshot.known_arrears,
            savings_above_reserve=snapshot.savings_above_reserve,
            reserve_gap=snapshot.reserve_gap,
            result_code=ResilienceResultCode(snapshot.resilience_result_code)
            if snapshot.resilience_result_code
            else None,
            warnings=tuple(snapshot.resilience_warnings),
        ),
    )


def get_effective_snapshot(session: Session, *, customer_id: uuid.UUID) -> ConfirmedSnapshotView | None:
    superseded_ids = select(ConfirmedSnapshot.supersedes_snapshot_id).where(
        ConfirmedSnapshot.customer_id == customer_id,
        ConfirmedSnapshot.supersedes_snapshot_id.is_not(None),
    )
    stmt = (
        select(ConfirmedSnapshot)
        .where(
            ConfirmedSnapshot.customer_id == customer_id,
            ConfirmedSnapshot.id.not_in(superseded_ids),
        )
        .order_by(ConfirmedSnapshot.statement_period.desc(), ConfirmedSnapshot.confirmed_at.desc())
        .limit(1)
    )
    snapshot = session.execute(stmt).scalar_one_or_none()
    if snapshot is None:
        return None
    return _to_view(snapshot)
