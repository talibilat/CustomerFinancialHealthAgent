from datetime import date, datetime, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

import pytest
from sqlalchemy.orm import Session

from customer_financial_health_api.domain.financial_health import (
    Frequency,
    MoneyEntry,
    calculate_monthly_position,
    calculate_resilience,
)
from customer_financial_health_api.domain.statement import validate_statement
from customer_financial_health_api.persistence.repository import (
    StaleStatementVersion,
    create_customer,
    get_editable_statement,
    save_confirmed_snapshot,
    save_editable_statement,
)

PERIOD = date(2026, 8, 1)


def payload(**overrides):
    base = {
        "statement_period": PERIOD.isoformat(),
        "income_entries": [
            {"entry_id": "i1", "description": "Wages", "amount": "2450.55", "frequency": "monthly"}
        ],
        "outgoing_entries": [
            {"entry_id": "o1", "description": "Rent", "amount": "950.05", "frequency": "monthly"},
            {"entry_id": "o2", "description": "Food", "amount": "120.00", "frequency": "weekly"},
        ],
        "repayment_commitments": [
            {"entry_id": "r1", "description": "Credit card", "amount": "75.25", "frequency": "monthly"}
        ],
    }
    base.update(overrides)
    return base


def test_editable_statement_round_trips_exact_decimals_and_original_frequencies(db_session):
    customer = create_customer(db_session)

    save_editable_statement(
        db_session,
        customer_id=customer.id,
        statement=validate_statement(payload()),
        expected_version=None,
    )
    db_session.commit()

    stored = get_editable_statement(db_session, customer_id=customer.id, statement_period=PERIOD)

    assert stored is not None
    assert stored.statement.income_entries[0].amount == Decimal("2450.55")
    assert stored.statement.outgoing_entries[1].amount == Decimal("120.00")
    assert stored.statement.outgoing_entries[1].frequency == Frequency.WEEKLY
    assert stored.statement.outgoing_entries[1].description == "Food"
    assert stored.statement.repayment_commitments[0].amount == Decimal("75.25")


def test_first_save_starts_at_version_one_and_each_save_advances_it(db_session):
    customer = create_customer(db_session)

    first = save_editable_statement(
        db_session, customer_id=customer.id, statement=validate_statement(payload()), expected_version=None
    )
    db_session.commit()
    assert first.version == 1

    second = save_editable_statement(
        db_session, customer_id=customer.id, statement=validate_statement(payload()), expected_version=1
    )
    db_session.commit()
    assert second.version == 2


def test_saving_against_a_stale_version_is_refused_and_changes_nothing(db_session):
    customer = create_customer(db_session)
    save_editable_statement(
        db_session, customer_id=customer.id, statement=validate_statement(payload()), expected_version=None
    )
    db_session.commit()

    changed = payload()
    changed["income_entries"][0]["amount"] = "9999.99"

    with pytest.raises(StaleStatementVersion):
        save_editable_statement(
            db_session,
            customer_id=customer.id,
            statement=validate_statement(changed),
            expected_version=99,
        )
    db_session.rollback()

    stored = get_editable_statement(db_session, customer_id=customer.id, statement_period=PERIOD)
    assert stored.version == 1
    assert stored.statement.income_entries[0].amount == Decimal("2450.55")


def test_concurrent_saves_cannot_both_overwrite_the_same_version(engine, db_session):
    customer = create_customer(db_session)
    customer_id = customer.id
    save_editable_statement(
        db_session, customer_id=customer_id, statement=validate_statement(payload()), expected_version=None
    )
    db_session.commit()

    first_session = Session(engine)
    second_started = Event()

    try:
        first = payload()
        first["income_entries"][0]["amount"] = "3000.00"
        save_editable_statement(
            first_session,
            customer_id=customer_id,
            statement=validate_statement(first),
            expected_version=1,
        )

        def attempt_second_save():
            with Session(engine) as second_session:
                second = payload()
                second["income_entries"][0]["amount"] = "4000.00"
                second_started.set()
                try:
                    save_editable_statement(
                        second_session,
                        customer_id=customer_id,
                        statement=validate_statement(second),
                        expected_version=1,
                    )
                    second_session.commit()
                    return "saved"
                except StaleStatementVersion:
                    second_session.rollback()
                    return "stale"

        with ThreadPoolExecutor(max_workers=1) as pool:
            second_result = pool.submit(attempt_second_save)
            assert second_started.wait(timeout=1)

            deadline = monotonic() + 1
            while not second_result.done() and monotonic() < deadline:
                sleep(0.01)

            first_session.commit()
            assert second_result.result(timeout=2) == "stale"
    finally:
        first_session.close()


def test_editable_statement_is_scoped_to_its_owning_customer(db_session):
    owner = create_customer(db_session)
    other = create_customer(db_session)
    save_editable_statement(
        db_session, customer_id=owner.id, statement=validate_statement(payload()), expected_version=None
    )
    db_session.commit()

    assert get_editable_statement(db_session, customer_id=other.id, statement_period=PERIOD) is None
    assert get_editable_statement(db_session, customer_id=owner.id, statement_period=PERIOD) is not None


def test_missing_editable_statement_returns_none_rather_than_an_empty_statement(db_session):
    customer = create_customer(db_session)

    assert get_editable_statement(db_session, customer_id=customer.id, statement_period=PERIOD) is None


def test_optional_resilience_and_looking_ahead_information_round_trips(db_session):
    customer = create_customer(db_session)
    statement = validate_statement(
        payload(
            resilience={
                "accessible_savings": "300.00",
                "protected_reserve": "1000.00",
                "current_account_balance": "-45.30",
            },
            looking_ahead={
                "irregular_costs": [
                    {"entry_id": "a1", "description": "Car insurance", "amount": "600.00", "frequency": "annual"}
                ],
                "protected_future_provisions": [
                    {"entry_id": "p1", "description": "Emergency fund", "amount": "25.00", "frequency": "monthly"}
                ],
                "expected_changes": [
                    {
                        "entry_id": "e1",
                        "description": "Shift reduction",
                        "kind": "income_decrease",
                        "amount": "200.00",
                        "frequency": "monthly",
                    }
                ],
            },
        )
    )

    save_editable_statement(
        db_session, customer_id=customer.id, statement=statement, expected_version=None
    )
    db_session.commit()

    stored = get_editable_statement(db_session, customer_id=customer.id, statement_period=PERIOD)

    assert stored.statement.resilience.accessible_savings == Decimal("300.00")
    assert stored.statement.resilience.current_account_balance == Decimal("-45.30")
    assert stored.statement.resilience.known_arrears is None
    assert stored.statement.looking_ahead.irregular_costs[0].amount == Decimal("600.00")
    assert stored.statement.looking_ahead.irregular_costs[0].frequency == Frequency.ANNUAL
    assert stored.statement.looking_ahead.protected_future_provisions[0].description == "Emergency fund"
    assert stored.statement.looking_ahead.expected_changes[0].kind.value == "income_decrease"


def test_saving_the_editable_statement_never_alters_a_confirmed_snapshot(db_session):
    customer = create_customer(db_session)
    income = [MoneyEntry(Decimal("2450.00"), Frequency.MONTHLY)]
    outgoings = [MoneyEntry(Decimal("950.00"), Frequency.MONTHLY)]
    snapshot = save_confirmed_snapshot(
        db_session,
        customer_id=customer.id,
        statement_period=PERIOD,
        confirmed_at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
        position=calculate_monthly_position(income, outgoings),
        income_entries=income,
        outgoing_entries=outgoings,
        resilience=calculate_resilience(),
    )
    db_session.commit()
    original_headroom = snapshot.monthly_headroom

    changed = payload()
    changed["income_entries"][0]["amount"] = "10.00"
    save_editable_statement(
        db_session, customer_id=customer.id, statement=validate_statement(changed), expected_version=None
    )
    db_session.commit()

    db_session.refresh(snapshot)
    assert snapshot.monthly_headroom == original_headroom
    assert snapshot.normalized_monthly_income == Decimal("2450.00")
