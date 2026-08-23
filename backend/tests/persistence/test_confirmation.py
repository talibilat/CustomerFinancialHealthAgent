from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Event
from time import monotonic, sleep

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_financial_health_api.domain.classification import (
    DisplayCategory,
    OutgoingTreatment,
    classify_outgoing,
)
from customer_financial_health_api.domain.statement import validate_statement
from customer_financial_health_api.persistence.models import ConfirmedSnapshot
from customer_financial_health_api.persistence.repository import (
    IdempotencyConflict,
    StaleStatementVersion,
    UnresolvedClassifications,
    confirm_statement,
    create_customer,
    get_effective_snapshot,
    save_editable_statement,
)

PERIOD = date(2026, 8, 1)
CONFIRMED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def payload(**overrides):
    base = {
        "statement_period": PERIOD.isoformat(),
        "income_entries": [
            {"entry_id": "i1", "description": "Wages", "amount": "2450.00", "frequency": "monthly"}
        ],
        "outgoing_entries": [
            {"entry_id": "o1", "description": "Rent", "amount": "950.00", "frequency": "monthly"}
        ],
        "repayment_commitments": [],
    }
    base.update(overrides)
    return base


def resolved_classifications(statement):
    return {
        entry.entry_id: classify_outgoing(entry.description, preferences=())
        for entry in statement.outgoing_entries
    }


def prepared(session, **overrides):
    """A customer with a saved editable statement ready to confirm."""
    customer = create_customer(session)
    statement = validate_statement(payload(**overrides))
    saved = save_editable_statement(
        session, customer_id=customer.id, statement=statement, expected_version=None
    )
    session.commit()
    return customer, statement, saved.version


def confirm(session, customer, statement, version, *, key="key-1", **kwargs):
    return confirm_statement(
        session,
        customer_id=customer.id,
        statement=statement,
        classifications=kwargs.pop("classifications", resolved_classifications(statement)),
        expected_version=version,
        idempotency_key=key,
        confirmed_at=kwargs.pop("confirmed_at", CONFIRMED_AT),
        **kwargs,
    )


class TestSuccessfulConfirmation:
    def test_confirmation_stores_the_reported_statement_and_its_results(self, db_session):
        customer, statement, version = prepared(db_session)

        confirm(db_session, customer, statement, version)
        db_session.commit()

        snapshot = get_effective_snapshot(db_session, customer_id=customer.id)
        assert snapshot.statement_period == PERIOD
        assert snapshot.normalized_monthly_income == Decimal("2450.00")
        assert snapshot.monthly_headroom == Decimal("1500.00")
        assert snapshot.calculation_policy_version == "normalization-policy-v1"
        assert snapshot.outgoing_entries[0].description == "Rent"
        assert snapshot.outgoing_entries[0].display_category == DisplayCategory.HOUSING

    def test_confirmation_time_is_aware_utc_and_separate_from_the_statement_period(self, db_session):
        customer, statement, version = prepared(db_session)

        confirm(db_session, customer, statement, version)
        db_session.commit()

        snapshot = get_effective_snapshot(db_session, customer_id=customer.id)
        assert snapshot.confirmed_at.tzinfo is not None
        assert snapshot.confirmed_at.utcoffset().total_seconds() == 0
        assert snapshot.confirmed_at.date() != snapshot.statement_period

    def test_a_second_confirmation_adds_history_and_never_edits_the_first(self, db_session):
        customer, statement, version = prepared(db_session)
        confirm(db_session, customer, statement, version)
        db_session.commit()
        first = get_effective_snapshot(db_session, customer_id=customer.id)

        changed = validate_statement(payload(income_entries=[
            {"entry_id": "i1", "description": "Wages", "amount": "2600.00", "frequency": "monthly"}
        ]))
        # Confirming retires the draft it was built from, so the next edit
        # starts from the version confirmation left behind.
        save_editable_statement(
            db_session, customer_id=customer.id, statement=changed, expected_version=2
        )
        db_session.commit()
        confirm(db_session, customer, changed, 3, key="key-2")
        db_session.commit()

        stored = db_session.execute(select(ConfirmedSnapshot)).scalars().all()
        assert len(stored) == 2
        original = next(s for s in stored if s.id == first.id)
        assert original.normalized_monthly_income == Decimal("2450.00")


class TestIdempotency:
    def test_repeating_the_same_request_returns_the_original_without_duplicating(self, db_session):
        customer, statement, version = prepared(db_session)
        first = confirm(db_session, customer, statement, version)
        db_session.commit()

        repeated = confirm(db_session, customer, statement, version)
        db_session.commit()

        assert repeated.id == first.id
        assert len(db_session.execute(select(ConfirmedSnapshot)).scalars().all()) == 1

    def test_reusing_a_key_with_a_different_request_is_a_conflict(self, db_session):
        customer, statement, version = prepared(db_session)
        confirm(db_session, customer, statement, version)
        db_session.commit()

        different = validate_statement(payload(income_entries=[
            {"entry_id": "i1", "description": "Wages", "amount": "9999.00", "frequency": "monthly"}
        ]))
        with pytest.raises(IdempotencyConflict):
            confirm(db_session, customer, different, version)
        db_session.rollback()

        assert len(db_session.execute(select(ConfirmedSnapshot)).scalars().all()) == 1

    def test_keys_are_scoped_to_their_customer(self, db_session):
        first_customer, first_statement, first_version = prepared(db_session)
        confirm(db_session, first_customer, first_statement, first_version)
        db_session.commit()

        second_customer, second_statement, second_version = prepared(db_session)
        # The same key text, a different customer: not a replay.
        confirm(db_session, second_customer, second_statement, second_version)
        db_session.commit()

        assert len(db_session.execute(select(ConfirmedSnapshot)).scalars().all()) == 2


class TestRefusals:
    def test_a_stale_statement_version_is_refused_and_writes_nothing(self, db_session):
        customer, statement, _ = prepared(db_session)

        with pytest.raises(StaleStatementVersion):
            confirm(db_session, customer, statement, 99)
        db_session.rollback()

        assert get_effective_snapshot(db_session, customer_id=customer.id) is None

    def test_an_unresolved_classification_blocks_confirmation_and_writes_nothing(self, db_session):
        customer, statement, version = prepared(
            db_session,
            outgoing_entries=[
                {"entry_id": "o1", "description": "Apple", "amount": "9.99", "frequency": "monthly"}
            ],
        )

        with pytest.raises(UnresolvedClassifications) as raised:
            confirm(db_session, customer, statement, version)
        db_session.rollback()

        assert raised.value.entry_ids == ("o1",)
        assert get_effective_snapshot(db_session, customer_id=customer.id) is None

    def test_confirmation_proceeds_once_the_customer_settles_the_ambiguous_entry(self, db_session):
        customer, statement, version = prepared(
            db_session,
            outgoing_entries=[
                {"entry_id": "o1", "description": "Apple", "amount": "9.99", "frequency": "monthly"}
            ],
        )
        settled = {
            "o1": classify_outgoing("Apple", preferences=()).confirmed_as(
                display_category=DisplayCategory.LEISURE_AND_HOBBIES,
                outgoing_treatment=OutgoingTreatment.FLEXIBLE_LIVING_COST,
            )
        }

        confirm(db_session, customer, statement, version, classifications=settled)
        db_session.commit()

        snapshot = get_effective_snapshot(db_session, customer_id=customer.id)
        assert snapshot.outgoing_entries[0].display_category == DisplayCategory.LEISURE_AND_HOBBIES


class TestAtomicity:
    def test_a_failure_partway_through_leaves_no_partial_history(self, db_session, monkeypatch):
        customer, statement, version = prepared(db_session)

        import customer_financial_health_api.persistence.repository as repo

        def explode(*args, **kwargs):
            raise RuntimeError("injected failure after the snapshot row")

        monkeypatch.setattr(repo, "_record_idempotent_confirmation", explode)

        with pytest.raises(RuntimeError):
            confirm(db_session, customer, statement, version)
        db_session.rollback()

        assert get_effective_snapshot(db_session, customer_id=customer.id) is None
        assert db_session.execute(select(ConfirmedSnapshot)).scalars().all() == []


class TestConcurrency:
    def test_two_simultaneous_confirmations_create_one_snapshot_or_a_safe_conflict(
        self, engine, db_session
    ):
        customer, statement, version = prepared(db_session)
        customer_id = customer.id
        started = Event()

        first_session = Session(engine)
        try:
            confirm_statement(
                first_session,
                customer_id=customer_id,
                statement=statement,
                classifications=resolved_classifications(statement),
                expected_version=version,
                idempotency_key="race-a",
                confirmed_at=CONFIRMED_AT,
            )

            def second_attempt():
                with Session(engine) as other:
                    started.set()
                    try:
                        confirm_statement(
                            other,
                            customer_id=customer_id,
                            statement=statement,
                            classifications=resolved_classifications(statement),
                            expected_version=version,
                            idempotency_key="race-b",
                            confirmed_at=CONFIRMED_AT,
                        )
                        other.commit()
                        return "confirmed"
                    except StaleStatementVersion:
                        other.rollback()
                        return "conflict"

            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(second_attempt)
                assert started.wait(timeout=1)
                deadline = monotonic() + 1
                while not pending.done() and monotonic() < deadline:
                    sleep(0.01)
                first_session.commit()
                assert pending.result(timeout=3) == "conflict"
        finally:
            first_session.close()

        assert len(db_session.execute(select(ConfirmedSnapshot)).scalars().all()) == 1
