from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Event
from time import monotonic, sleep

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.statement import validate_statement
from customer_financial_health_api.persistence.models import ConfirmedSnapshot
from customer_financial_health_api.persistence.repository import (
    CorrectionReasonInvalid,
    SnapshotAlreadySuperseded,
    confirm_statement,
    correct_snapshot,
    create_customer,
    list_confirmed_history,
    list_effective_series,
    save_editable_statement,
)

PERIOD = date(2026, 8, 1)
CONFIRMED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc)
REASON = "I entered the wrong rent amount."


def payload(rent="950.00", **overrides):
    base = {
        "statement_period": PERIOD.isoformat(),
        "income_entries": [
            {"entry_id": "i1", "description": "Wages", "amount": "2450.00", "frequency": "monthly"}
        ],
        "outgoing_entries": [
            {"entry_id": "o1", "description": "Rent", "amount": rent, "frequency": "monthly"}
        ],
        "repayment_commitments": [],
    }
    base.update(overrides)
    return base


def classifications(statement):
    return {
        e.entry_id: classify_outgoing(e.description, preferences=())
        for e in statement.outgoing_entries
    }


def confirmed(session):
    """A customer with one confirmed snapshot."""
    customer = create_customer(session)
    statement = validate_statement(payload())
    saved = save_editable_statement(
        session, customer_id=customer.id, statement=statement, expected_version=None
    )
    session.commit()
    snapshot = confirm_statement(
        session,
        customer_id=customer.id,
        statement=statement,
        classifications=classifications(statement),
        expected_version=saved.version,
        idempotency_key="confirm-1",
        confirmed_at=CONFIRMED_AT,
    )
    session.commit()
    return customer, snapshot


def correct(session, customer, supersedes_id, *, rent="1100.00", reason=REASON, key="fix-1",
            confirmed_at=LATER):
    statement = validate_statement(payload(rent=rent))
    return correct_snapshot(
        session,
        customer_id=customer.id,
        supersedes_snapshot_id=supersedes_id,
        statement=statement,
        classifications=classifications(statement),
        correction_reason=reason,
        idempotency_key=key,
        confirmed_at=confirmed_at,
    )


class TestCorrectionCreatesASuccessor:
    def test_the_original_is_untouched_and_the_correction_supersedes_it(self, db_session):
        customer, original = confirmed(db_session)

        correction = correct(db_session, customer, original.id)
        db_session.commit()

        rows = {s.id: s for s in db_session.execute(select(ConfirmedSnapshot)).scalars()}
        assert len(rows) == 2
        assert rows[original.id].normalized_monthly_outgoings == Decimal("950.00")
        assert rows[original.id].supersedes_snapshot_id is None
        assert rows[correction.id].supersedes_snapshot_id == original.id
        assert rows[correction.id].correction_reason == REASON

    def test_the_correction_keeps_the_original_statement_period(self, db_session):
        customer, original = confirmed(db_session)

        correction = correct(db_session, customer, original.id)
        db_session.commit()

        # Confirmed in September, but it still describes August.
        assert correction.statement_period == PERIOD
        assert correction.confirmed_at.month == 9

    def test_the_correction_becomes_effective_and_the_original_stays_in_history(self, db_session):
        customer, original = confirmed(db_session)

        correction = correct(db_session, customer, original.id)
        db_session.commit()

        series = list_effective_series(db_session, customer_id=customer.id)
        history = list_confirmed_history(db_session, customer_id=customer.id)

        assert [s.id for s in series] == [correction.id]
        assert {s.id for s in history.snapshots} == {original.id, correction.id}


class TestCorrectionChains:
    def test_a_correction_can_itself_be_corrected_leaving_one_effective_snapshot(self, db_session):
        customer, original = confirmed(db_session)
        first = correct(db_session, customer, original.id, rent="1100.00")
        db_session.commit()

        second = correct(db_session, customer, first.id, rent="1200.00", key="fix-2")
        db_session.commit()

        series = list_effective_series(db_session, customer_id=customer.id)
        assert [s.id for s in series] == [second.id]
        assert list_confirmed_history(db_session, customer_id=customer.id).total == 3

    def test_correcting_an_already_superseded_snapshot_is_refused(self, db_session):
        customer, original = confirmed(db_session)
        correct(db_session, customer, original.id)
        db_session.commit()

        with pytest.raises(SnapshotAlreadySuperseded):
            correct(db_session, customer, original.id, key="fix-2")
        db_session.rollback()

        assert list_confirmed_history(db_session, customer_id=customer.id).total == 2


class TestReasonValidation:
    @pytest.mark.parametrize("reason", ["", "   ", "\t\n"])
    def test_a_blank_reason_is_refused(self, db_session, reason):
        customer, original = confirmed(db_session)

        with pytest.raises(CorrectionReasonInvalid):
            correct(db_session, customer, original.id, reason=reason)
        db_session.rollback()

        assert list_confirmed_history(db_session, customer_id=customer.id).total == 1

    def test_an_excessively_long_reason_is_refused(self, db_session):
        customer, original = confirmed(db_session)

        with pytest.raises(CorrectionReasonInvalid):
            correct(db_session, customer, original.id, reason="x" * 501)
        db_session.rollback()

        assert list_confirmed_history(db_session, customer_id=customer.id).total == 1


class TestOwnership:
    def test_a_customer_cannot_correct_another_customers_snapshot(self, db_session):
        owner, original = confirmed(db_session)
        stranger = create_customer(db_session)
        db_session.commit()

        with pytest.raises(Exception):
            correct(db_session, stranger, original.id)
        db_session.rollback()

        rows = db_session.execute(select(ConfirmedSnapshot)).scalars().all()
        assert len(rows) == 1
        assert rows[0].supersedes_snapshot_id is None


class TestConcurrency:
    def test_two_corrections_of_one_snapshot_permit_only_one_successor(self, engine, db_session):
        customer, original = confirmed(db_session)
        customer_id, original_id = customer.id, original.id
        started = Event()

        first_session = Session(engine)
        try:
            statement = validate_statement(payload(rent="1100.00"))
            correct_snapshot(
                first_session,
                customer_id=customer_id,
                supersedes_snapshot_id=original_id,
                statement=statement,
                classifications=classifications(statement),
                correction_reason=REASON,
                idempotency_key="race-a",
                confirmed_at=LATER,
            )

            def second_attempt():
                with Session(engine) as other:
                    other_statement = validate_statement(payload(rent="1200.00"))
                    started.set()
                    try:
                        correct_snapshot(
                            other,
                            customer_id=customer_id,
                            supersedes_snapshot_id=original_id,
                            statement=other_statement,
                            classifications=classifications(other_statement),
                            correction_reason=REASON,
                            idempotency_key="race-b",
                            confirmed_at=LATER,
                        )
                        other.commit()
                        return "corrected"
                    except SnapshotAlreadySuperseded:
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

        assert list_confirmed_history(db_session, customer_id=customer_id).total == 2
        assert len(list_effective_series(db_session, customer_id=customer_id)) == 1


class TestAtomicity:
    def test_a_failure_while_linking_leaves_the_old_effective_state(self, db_session, monkeypatch):
        customer, original = confirmed(db_session)

        import customer_financial_health_api.persistence.repository as repo

        monkeypatch.setattr(
            repo,
            "_record_idempotent_confirmation",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected failure")),
        )

        with pytest.raises(RuntimeError):
            correct(db_session, customer, original.id)
        db_session.rollback()

        assert list_confirmed_history(db_session, customer_id=customer.id).total == 1
        assert [s.id for s in list_effective_series(db_session, customer_id=customer.id)] == [
            original.id
        ]
