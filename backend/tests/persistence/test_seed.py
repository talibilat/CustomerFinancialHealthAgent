from sqlalchemy import select

from customer_financial_health_api.persistence.models import Customer
from customer_financial_health_api.persistence.repository import get_effective_snapshot
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
