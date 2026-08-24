from datetime import date, datetime, timezone
from decimal import Decimal

from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.financial_health import (
    Frequency,
    calculate_monthly_position,
    calculate_resilience,
)
from customer_financial_health_api.domain.statement import StatementEntry
from customer_financial_health_api.persistence.repository import (
    create_customer,
    list_confirmed_history,
    list_effective_series,
    save_confirmed_snapshot,
)


def confirm(session, customer, period, confirmed_at, *, income="2450.00", rent="950.00",
            supersedes=None):
    income_entries = [StatementEntry("i1", "Wages", Decimal(income), Frequency.MONTHLY)]
    outgoing_entries = [StatementEntry("o1", "Rent", Decimal(rent), Frequency.MONTHLY)]
    return save_confirmed_snapshot(
        session,
        customer_id=customer.id,
        statement_period=date.fromisoformat(period),
        confirmed_at=confirmed_at,
        position=calculate_monthly_position(
            [e.as_money_entry() for e in income_entries],
            [e.as_money_entry() for e in outgoing_entries],
        ),
        income_entries=income_entries,
        outgoing_entries=outgoing_entries,
        resilience=calculate_resilience(),
        classifications={"o1": classify_outgoing("Rent", preferences=())},
        supersedes_snapshot_id=supersedes,
    )


def at(day, hour=9):
    return datetime(2026, 9, day, hour, 0, tzinfo=timezone.utc)


class TestOrdering:
    def test_history_is_ordered_by_period_then_confirmation_time_not_insertion(self, db_session):
        customer = create_customer(db_session)
        # Deliberately inserted out of order.
        confirm(db_session, customer, "2026-07-01", at(3))
        confirm(db_session, customer, "2026-09-01", at(1))
        confirm(db_session, customer, "2026-08-01", at(2))
        db_session.commit()

        page = list_confirmed_history(db_session, customer_id=customer.id)

        assert [s.statement_period.isoformat() for s in page.snapshots] == [
            "2026-09-01",
            "2026-08-01",
            "2026-07-01",
        ]

    def test_two_confirmations_in_one_period_order_by_confirmation_time(self, db_session):
        customer = create_customer(db_session)
        first = confirm(db_session, customer, "2026-08-01", at(1))
        confirm(db_session, customer, "2026-08-01", at(5), income="2600.00")
        db_session.commit()

        page = list_confirmed_history(db_session, customer_id=customer.id)

        assert len(page.snapshots) == 2
        assert page.snapshots[0].confirmed_at > page.snapshots[1].confirmed_at
        assert page.snapshots[1].id == first.id


class TestEffectiveSeries:
    def test_the_series_takes_one_snapshot_per_period_while_history_keeps_all(self, db_session):
        customer = create_customer(db_session)
        original = confirm(db_session, customer, "2026-08-01", at(1))
        correction = confirm(
            db_session, customer, "2026-08-01", at(5), income="2600.00", supersedes=original.id
        )
        db_session.commit()

        series = list_effective_series(db_session, customer_id=customer.id)
        history = list_confirmed_history(db_session, customer_id=customer.id)

        assert [s.id for s in series] == [correction.id]
        assert len(history.snapshots) == 2

    def test_the_series_is_ordered_oldest_first_for_reading_across_time(self, db_session):
        customer = create_customer(db_session)
        confirm(db_session, customer, "2026-09-01", at(1))
        confirm(db_session, customer, "2026-07-01", at(2))
        db_session.commit()

        series = list_effective_series(db_session, customer_id=customer.id)

        assert [s.statement_period.isoformat() for s in series] == ["2026-07-01", "2026-09-01"]


class TestPagination:
    def test_pagination_reports_the_total_and_keeps_stable_ordering(self, db_session):
        customer = create_customer(db_session)
        for day, period in enumerate(["2026-06-01", "2026-07-01", "2026-08-01"], start=1):
            confirm(db_session, customer, period, at(day))
        db_session.commit()

        first = list_confirmed_history(db_session, customer_id=customer.id, limit=2, offset=0)
        second = list_confirmed_history(db_session, customer_id=customer.id, limit=2, offset=2)

        assert first.total == 3
        assert [s.statement_period.isoformat() for s in first.snapshots] == [
            "2026-08-01",
            "2026-07-01",
        ]
        assert [s.statement_period.isoformat() for s in second.snapshots] == ["2026-06-01"]

    def test_a_page_beyond_the_end_is_empty_rather_than_an_error(self, db_session):
        customer = create_customer(db_session)
        confirm(db_session, customer, "2026-08-01", at(1))
        db_session.commit()

        page = list_confirmed_history(db_session, customer_id=customer.id, limit=10, offset=50)

        assert page.snapshots == ()
        assert page.total == 1

    def test_no_history_is_an_empty_page_not_an_error(self, db_session):
        customer = create_customer(db_session)

        page = list_confirmed_history(db_session, customer_id=customer.id)

        assert page.snapshots == ()
        assert page.total == 0


class TestOwnershipAndPersistedPolicy:
    def test_history_never_includes_another_customers_snapshots(self, db_session):
        owner = create_customer(db_session)
        other = create_customer(db_session)
        confirm(db_session, owner, "2026-08-01", at(1))
        db_session.commit()

        assert list_confirmed_history(db_session, customer_id=other.id).total == 0
        assert list_confirmed_history(db_session, customer_id=owner.id).total == 1

    def test_history_reads_the_policy_versions_that_were_stored(self, db_session):
        customer = create_customer(db_session)
        snapshot = confirm(db_session, customer, "2026-08-01", at(1))
        # Simulate a snapshot confirmed under an older policy.
        snapshot.calculation_policy_version = "normalization-policy-v0"
        db_session.commit()

        page = list_confirmed_history(db_session, customer_id=customer.id)

        assert page.snapshots[0].calculation_policy_version == "normalization-policy-v0"

    def test_history_reads_the_labels_and_categories_that_were_stored(self, db_session):
        customer = create_customer(db_session)
        confirm(db_session, customer, "2026-08-01", at(1))
        db_session.commit()

        snapshot = list_confirmed_history(db_session, customer_id=customer.id).snapshots[0]

        assert snapshot.outgoing_entries[0].description == "Rent"
        assert snapshot.outgoing_entries[0].display_category.value == "housing"
