from datetime import date, datetime, timezone
from decimal import Decimal

from customer_financial_health_api.domain.financial_health import (
    Frequency,
    MoneyEntry,
    calculate_monthly_position,
    calculate_resilience,
)
from customer_financial_health_api.persistence.repository import (
    create_customer,
    get_effective_snapshot,
    save_confirmed_snapshot,
)


def test_resilience_values_round_trip_with_decimal_precision(db_session):
    customer = create_customer(db_session)
    db_session.commit()

    position = calculate_monthly_position(
        income_entries=[MoneyEntry(Decimal("1500.00"), Frequency.MONTHLY)],
        outgoing_entries=[MoneyEntry(Decimal("1000.00"), Frequency.MONTHLY)],
    )
    resilience = calculate_resilience(
        accessible_savings=Decimal("753.42"),
        protected_reserve=Decimal("500.00"),
        current_account_balance=Decimal("-42.17"),
        known_arrears=Decimal("120.00"),
    )

    save_confirmed_snapshot(
        db_session,
        customer_id=customer.id,
        statement_period=date(2026, 8, 1),
        confirmed_at=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        position=position,
        income_entries=[MoneyEntry(Decimal("1500.00"), Frequency.MONTHLY)],
        outgoing_entries=[MoneyEntry(Decimal("1000.00"), Frequency.MONTHLY)],
        resilience=resilience,
    )
    db_session.commit()

    fetched = get_effective_snapshot(db_session, customer_id=customer.id)

    assert fetched.resilience.accessible_savings == Decimal("753.42")
    assert fetched.resilience.protected_reserve == Decimal("500.00")
    assert fetched.resilience.current_account_balance == Decimal("-42.17")
    assert fetched.resilience.known_arrears == Decimal("120.00")
    assert fetched.resilience.savings_above_reserve == Decimal("253.42")
    assert fetched.resilience.reserve_gap == Decimal("0.00")
    assert fetched.resilience.result_code.value == "above_reserve"


def test_missing_resilience_information_round_trips_as_limitation(db_session):
    customer = create_customer(db_session)
    db_session.commit()

    position = calculate_monthly_position(
        income_entries=[MoneyEntry(Decimal("1500.00"), Frequency.MONTHLY)],
        outgoing_entries=[],
    )
    resilience = calculate_resilience()

    save_confirmed_snapshot(
        db_session,
        customer_id=customer.id,
        statement_period=date(2026, 8, 1),
        confirmed_at=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        position=position,
        income_entries=[MoneyEntry(Decimal("1500.00"), Frequency.MONTHLY)],
        outgoing_entries=[],
        resilience=resilience,
    )
    db_session.commit()

    fetched = get_effective_snapshot(db_session, customer_id=customer.id)

    assert fetched.resilience.result_code is None
    assert "resilience_info_missing" in fetched.resilience.warnings
    assert fetched.monthly_headroom == Decimal("1500.00")
