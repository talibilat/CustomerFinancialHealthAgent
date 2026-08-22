from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_financial_health_api.domain.financial_health import (
    Frequency,
    MoneyEntry,
    calculate_monthly_position,
)
from customer_financial_health_api.persistence.models import Customer
from customer_financial_health_api.persistence.repository import (
    create_customer,
    save_confirmed_snapshot,
)


def seed_demo_data(session: Session) -> None:
    existing = session.execute(select(Customer).limit(1)).scalar_one_or_none()
    if existing is not None:
        return

    customer = create_customer(session)

    income_entries = [MoneyEntry(Decimal("2450.00"), Frequency.MONTHLY)]
    outgoing_entries = [
        MoneyEntry(Decimal("950.00"), Frequency.MONTHLY),
        MoneyEntry(Decimal("120.00"), Frequency.WEEKLY),
        MoneyEntry(Decimal("45.00"), Frequency.FOUR_WEEKLY),
    ]
    position = calculate_monthly_position(income_entries, outgoing_entries)

    save_confirmed_snapshot(
        session,
        customer_id=customer.id,
        statement_period=date(2026, 8, 1),
        confirmed_at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
        position=position,
        income_entries=income_entries,
        outgoing_entries=outgoing_entries,
    )
