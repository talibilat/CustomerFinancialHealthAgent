from datetime import date

from sqlalchemy import select

from customer_financial_health_api.persistence.models import Customer
from customer_financial_health_api.domain.statement import preview_statement
from customer_financial_health_api.persistence.repository import (
    get_editable_statement,
    get_effective_snapshot,
)
from customer_financial_health_api.persistence.seed import seed_demo_data


def test_seed_creates_one_customer_with_one_confirmed_snapshot(db_session):
    seed_demo_data(db_session)
    db_session.commit()

    customers = db_session.execute(select(Customer)).scalars().all()
    assert len(customers) == 1

    snapshot = get_effective_snapshot(db_session, customer_id=customers[0].id)
    assert snapshot is not None
    assert snapshot.income_entries
    assert snapshot.outgoing_entries


def test_seed_is_idempotent(db_session):
    seed_demo_data(db_session)
    db_session.commit()
    seed_demo_data(db_session)
    db_session.commit()

    customers = db_session.execute(select(Customer)).scalars().all()
    assert len(customers) == 1


def test_seed_creates_an_editable_statement_matching_the_confirmed_snapshot(db_session):
    seed_demo_data(db_session)
    db_session.commit()

    customer = db_session.execute(select(Customer)).scalars().one()
    snapshot = get_effective_snapshot(db_session, customer_id=customer.id)
    editable = get_editable_statement(
        db_session, customer_id=customer.id, statement_period=snapshot.statement_period
    )

    assert editable is not None
    assert editable.version == 1
    # The editable statement starts from what the customer already confirmed.
    assert preview_statement(editable.statement).position.monthly_headroom == snapshot.monthly_headroom
    # Every reported line carries a description the customer can recognise.
    assert all(entry.description for entry in editable.statement.income_entries)
    assert all(entry.description for entry in editable.statement.outgoing_entries)


def test_seeded_editable_statement_keeps_resilience_and_is_idempotent(db_session):
    seed_demo_data(db_session)
    db_session.commit()
    seed_demo_data(db_session)
    db_session.commit()

    customer = db_session.execute(select(Customer)).scalars().one()
    editable = get_editable_statement(
        db_session, customer_id=customer.id, statement_period=date(2026, 8, 1)
    )

    assert editable.version == 1
    assert editable.statement.resilience.accessible_savings is not None
    assert editable.statement.resilience.current_account_balance is not None
