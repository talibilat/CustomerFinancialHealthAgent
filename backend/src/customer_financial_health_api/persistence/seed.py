from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_financial_health_api.domain.financial_health import (
    Frequency,
    MoneyEntry,
    calculate_monthly_position,
    calculate_resilience,
)
from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.statement import (
    FinancialStatement,
    LookingAheadInput,
    ResilienceInput,
    StatementEntry,
)
from customer_financial_health_api.persistence.models import Customer
from customer_financial_health_api.persistence.repository import (
    create_customer,
    save_confirmed_snapshot,
    save_editable_statement,
)

STATEMENT_PERIOD = date(2026, 8, 1)

# One fictional customer's reported statement. The confirmed snapshot and the
# editable statement are both built from this, so the reviewer starts from a
# statement that already matches their confirmed position.
INCOME_ENTRIES = (
    StatementEntry("income-1", "Wages", Decimal("2450.00"), Frequency.MONTHLY),
)
OUTGOING_ENTRIES = (
    StatementEntry("outgoing-1", "Rent", Decimal("950.00"), Frequency.MONTHLY),
    StatementEntry("outgoing-2", "Food and housekeeping", Decimal("120.00"), Frequency.WEEKLY),
    StatementEntry("outgoing-3", "Mobile and broadband", Decimal("45.00"), Frequency.FOUR_WEEKLY),
)
REPAYMENT_COMMITMENTS: tuple[StatementEntry, ...] = ()


def seed_demo_data(session: Session) -> None:
    existing = session.execute(select(Customer).limit(1)).scalar_one_or_none()
    if existing is not None:
        return

    customer = create_customer(session)

    income_entries = list(INCOME_ENTRIES)
    outgoing_entries = list(OUTGOING_ENTRIES + REPAYMENT_COMMITMENTS)
    position = calculate_monthly_position(
        [entry.as_money_entry() for entry in income_entries],
        [entry.as_money_entry() for entry in outgoing_entries],
    )
    # The seeded outgoings all resolve from global rules, with no provider.
    classifications = {
        entry.entry_id: classify_outgoing(entry.description, preferences=())
        for entry in outgoing_entries
    }

    # Deliberately a mixed picture: positive monthly headroom, but accessible
    # savings sit below the customer's protected reserve, and the current
    # account is slightly overdrawn.
    resilience_input = ResilienceInput(
        accessible_savings=Decimal("300.00"),
        protected_reserve=Decimal("1000.00"),
        current_account_balance=Decimal("-45.30"),
    )
    resilience = calculate_resilience(
        accessible_savings=resilience_input.accessible_savings,
        protected_reserve=resilience_input.protected_reserve,
        current_account_balance=resilience_input.current_account_balance,
        known_arrears=resilience_input.known_arrears,
    )

    save_confirmed_snapshot(
        session,
        customer_id=customer.id,
        statement_period=STATEMENT_PERIOD,
        confirmed_at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
        position=position,
        income_entries=income_entries,
        outgoing_entries=outgoing_entries,
        resilience=resilience,
        classifications=classifications,
        repayment_commitment_entry_ids={
            entry.entry_id for entry in REPAYMENT_COMMITMENTS
        },
    )

    save_editable_statement(
        session,
        customer_id=customer.id,
        statement=FinancialStatement(
            statement_period=STATEMENT_PERIOD,
            income_entries=INCOME_ENTRIES,
            outgoing_entries=OUTGOING_ENTRIES,
            repayment_commitments=REPAYMENT_COMMITMENTS,
            resilience=resilience_input,
            # Looking-ahead information is deliberately absent so the reviewer
            # sees a genuine limitation rather than an invented default.
            looking_ahead=LookingAheadInput(),
        ),
        expected_version=None,
    )
