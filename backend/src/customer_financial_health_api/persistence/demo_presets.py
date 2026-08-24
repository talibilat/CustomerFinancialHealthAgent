"""Controlled fictional states for reviewing difficult customer journeys."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy.orm import Session

from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.financial_health import (
    Frequency,
    calculate_monthly_position,
    calculate_resilience,
)
from customer_financial_health_api.domain.statement import (
    FinancialStatement,
    ResilienceInput,
    StatementEntry,
)
from customer_financial_health_api.persistence.models import DemoState
from customer_financial_health_api.persistence.repository import (
    create_customer,
    save_confirmed_snapshot,
    save_editable_statement,
)


@dataclass(frozen=True)
class DemoPreset:
    code: str
    label: str
    description: str


DEMO_PRESETS = (
    DemoPreset("zero_income", "Zero income", "No income is reported while protected living costs continue."),
    DemoPreset("reported_shortfall", "Reported shortfall", "Reported monthly outgoings exceed income by an exact amount."),
    DemoPreset("protected_outgoings_not_covered", "Protected outgoings not covered", "Protected living costs alone exceed reported income."),
    DemoPreset("mixed_resilience", "Mixed resilience", "Monthly cash flow is positive while savings remain below the protected reserve."),
    DemoPreset("repayment_near_buffer", "Repayment near the buffer", "A positive position leaves only a small margin above the protected monthly buffer."),
    DemoPreset("ambiguous_apple", "Ambiguous Apple classification", "An Apple outgoing waits for the customer to explain what it was for."),
    DemoPreset("improving_history", "Improving history", "Three fictional periods show an improving monthly position without inventing a cause."),
    DemoPreset("correction", "Correction", "A corrected snapshot supersedes the original while both remain in history."),
    DemoPreset("azure_unavailable", "Azure unavailable", "The core journey remains usable with deterministic results and manual classification."),
)

PRESET_CODES = frozenset(preset.code for preset in DEMO_PRESETS)
FIXED_CONFIRMED_AT = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def _entry(key: str, description: str, amount: str) -> StatementEntry:
    return StatementEntry(key, description, Decimal(amount), Frequency.MONTHLY)


def _statement(
    period: date,
    income: tuple[StatementEntry, ...],
    outgoings: tuple[StatementEntry, ...],
    *,
    savings: str | None = None,
    reserve: str | None = None,
) -> FinancialStatement:
    return FinancialStatement(
        statement_period=period,
        income_entries=income,
        outgoing_entries=outgoings,
        repayment_commitments=(),
        resilience=ResilienceInput(
            accessible_savings=Decimal(savings) if savings is not None else None,
            protected_reserve=Decimal(reserve) if reserve is not None else None,
        ),
    )


def _resolved_classifications(statement: FinancialStatement):
    return {
        entry.entry_id: result
        for entry in statement.outgoing_entries
        if (result := classify_outgoing(entry.description)).is_resolved
    }


def _save_snapshot(
    session: Session,
    customer_id: uuid.UUID,
    statement: FinancialStatement,
    *,
    confirmed_at: datetime = FIXED_CONFIRMED_AT,
    supersedes_snapshot_id: uuid.UUID | None = None,
):
    position = calculate_monthly_position(
        [entry.as_money_entry() for entry in statement.income_entries],
        [entry.as_money_entry() for entry in statement.outgoing_entries],
    )
    resilience = calculate_resilience(
        accessible_savings=statement.resilience.accessible_savings,
        protected_reserve=statement.resilience.protected_reserve,
    )
    return save_confirmed_snapshot(
        session,
        customer_id=customer_id,
        statement_period=statement.statement_period,
        confirmed_at=confirmed_at,
        position=position,
        income_entries=statement.income_entries,
        outgoing_entries=statement.outgoing_entries,
        resilience=resilience,
        classifications=_resolved_classifications(statement),
        supersedes_snapshot_id=supersedes_snapshot_id,
    )


def _preset_statement(code: str) -> FinancialStatement:
    period = date(2026, 8, 1)
    wage = (_entry("income-1", "Wages", "2450.00"),)
    if code == "zero_income":
        return _statement(period, (), (_entry("outgoing-1", "Rent", "650.00"),))
    if code == "reported_shortfall":
        return _statement(period, (_entry("income-1", "Wages", "1000.00"),), (
            _entry("outgoing-1", "Rent", "700.00"),
            _entry("outgoing-2", "Gym", "300.01"),
        ))
    if code == "protected_outgoings_not_covered":
        return _statement(period, (_entry("income-1", "Wages", "900.00"),), (
            _entry("outgoing-1", "Rent", "950.00"),
            _entry("outgoing-2", "Groceries", "100.00"),
        ))
    if code == "mixed_resilience":
        return _statement(period, (_entry("income-1", "Wages", "2000.00"),), (
            _entry("outgoing-1", "Rent", "1500.00"),
        ), savings="200.00", reserve="1000.00")
    if code == "repayment_near_buffer":
        return _statement(period, wage, (
            _entry("outgoing-1", "Rent", "950.00"),
            _entry("outgoing-2", "Groceries", "500.00"),
            _entry("outgoing-3", "Credit card repayment", "700.00"),
        ), savings="1000.00", reserve="1000.00")
    if code == "ambiguous_apple":
        return _statement(period, wage, (
            _entry("outgoing-1", "Rent", "950.00"),
            _entry("outgoing-2", "Apple", "42.50"),
        ))
    if code == "azure_unavailable":
        return _statement(period, wage, (
            _entry("outgoing-1", "Rent", "950.00"),
            _entry("outgoing-2", "Weekend pottery", "35.00"),
        ))
    return _statement(period, wage, (
        _entry("outgoing-1", "Rent", "950.00"),
        _entry("outgoing-2", "Groceries", "520.00"),
    ), savings="300.00", reserve="1000.00")


def activate_demo_preset(session: Session, preset_code: str) -> uuid.UUID:
    """Atomically select a fresh fictional aggregate without deleting prior data."""
    if preset_code not in PRESET_CODES:
        raise ValueError("unknown demo preset")

    state = session.get(DemoState, 1)
    if state is not None and state.active_preset == preset_code:
        return state.active_customer_id

    customer = create_customer(session)
    editable = _preset_statement(preset_code)

    if preset_code == "improving_history":
        for index, (period, income, outgoings) in enumerate((
            (date(2026, 6, 1), "1800.00", "1950.00"),
            (date(2026, 7, 1), "2000.00", "1900.00"),
            (date(2026, 8, 1), "2200.00", "1850.00"),
        )):
            item = _statement(period, (_entry(f"income-{index}", "Wages", income),), (
                _entry(f"outgoing-{index}", "Rent", outgoings),
            ))
            _save_snapshot(
                session,
                customer.id,
                item,
                confirmed_at=datetime(2026, 6 + index, 1, 9, 0, tzinfo=timezone.utc),
            )
        editable = _statement(date(2026, 8, 1), (_entry("income-2", "Wages", "2200.00"),), (
            _entry("outgoing-2", "Rent", "1850.00"),
        ))
    elif preset_code == "correction":
        original_statement = _statement(date(2026, 8, 1), (
            _entry("income-1", "Wages", "2000.00"),
        ), (_entry("outgoing-1", "Rent", "1000.00"),))
        original = _save_snapshot(session, customer.id, original_statement)
        editable = _statement(date(2026, 8, 1), (
            _entry("income-1", "Wages", "2000.00"),
        ), (_entry("outgoing-1", "Rent", "1100.00"),))
        correction = _save_snapshot(
            session,
            customer.id,
            editable,
            confirmed_at=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
            supersedes_snapshot_id=original.id,
        )
        correction.correction_reason = "Fictional rent amount corrected for the demonstration."
    elif preset_code in {"ambiguous_apple", "azure_unavailable"}:
        confirmed = _statement(editable.statement_period, editable.income_entries, (
            editable.outgoing_entries[0],
        ))
        _save_snapshot(session, customer.id, confirmed)
    else:
        _save_snapshot(session, customer.id, editable)

    save_editable_statement(
        session,
        customer_id=customer.id,
        statement=editable,
        expected_version=None,
        classifications=_resolved_classifications(editable),
    )
    if state is None:
        session.add(DemoState(id=1, active_customer_id=customer.id, active_preset=preset_code))
    else:
        state.active_customer_id = customer.id
        state.active_preset = preset_code
    session.flush()
    return customer.id
