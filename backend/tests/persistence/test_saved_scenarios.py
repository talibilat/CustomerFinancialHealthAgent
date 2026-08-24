from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.repayment import ScenarioMode
from customer_financial_health_api.domain.statement import validate_statement
from customer_financial_health_api.persistence.models import RepaymentScenario
from customer_financial_health_api.persistence.repository import (
    IdempotencyConflict,
    ScenarioBasisNotCurrent,
    ScenarioNotFound,
    confirm_statement,
    correct_snapshot,
    create_customer,
    get_repayment_scenario,
    get_editable_statement,
    get_effective_snapshot,
    list_repayment_scenarios,
    save_editable_statement,
    save_repayment_scenario,
)

PERIOD = date(2026, 8, 1)
CONFIRMED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
SAVED_AT = datetime(2026, 8, 23, 9, 30, tzinfo=timezone.utc)


def statement_payload(*, rent: str = "950.00") -> dict:
    return {
        "statement_period": PERIOD.isoformat(),
        "income_entries": [
            {
                "entry_id": "income-1",
                "description": "Wages",
                "amount": "2450.00",
                "frequency": "monthly",
            }
        ],
        "outgoing_entries": [
            {
                "entry_id": "outgoing-1",
                "description": "Rent",
                "amount": rent,
                "frequency": "monthly",
            }
        ],
        "repayment_commitments": [
            {
                "entry_id": "commitment-1",
                "description": "Credit card repayment",
                "amount": "75.25",
                "frequency": "monthly",
            }
        ],
    }


def confirmed_basis(session):
    customer = create_customer(session)
    statement = validate_statement(statement_payload())
    classifications = {
        entry.entry_id: classify_outgoing(entry.description, preferences=())
        for entry in (*statement.outgoing_entries, *statement.repayment_commitments)
    }
    editable = save_editable_statement(
        session,
        customer_id=customer.id,
        statement=statement,
        expected_version=None,
        classifications=classifications,
    )
    session.commit()
    snapshot = confirm_statement(
        session,
        customer_id=customer.id,
        statement=statement,
        classifications=classifications,
        expected_version=editable.version,
        idempotency_key="confirm-basis",
        confirmed_at=CONFIRMED_AT,
    )
    session.commit()
    return customer, snapshot


def save_additional(session, customer, snapshot, **overrides):
    values = {
        "customer_id": customer.id,
        "basis_snapshot_id": snapshot.id,
        "mode": ScenarioMode.ADDITIONAL,
        "selected_existing_commitment_id": None,
        "proposed_repayment": Decimal("100.01"),
        "protected_monthly_buffer": Decimal("200.00"),
        "idempotency_key": "save-scenario-1",
        "created_at": SAVED_AT,
    }
    values.update(overrides)
    return save_repayment_scenario(session, **values)


class TestSavedScenarioRecord:
    def test_an_explicit_save_persists_the_complete_deterministic_comparison(self, db_session):
        customer, snapshot = confirmed_basis(db_session)
        original_basis = get_effective_snapshot(db_session, customer_id=customer.id)
        original_statement = get_editable_statement(
            db_session, customer_id=customer.id, statement_period=PERIOD
        )

        saved = save_additional(db_session, customer, snapshot)
        db_session.commit()

        assert saved.customer_id == customer.id
        assert saved.basis_snapshot_id == snapshot.id
        assert saved.mode is ScenarioMode.ADDITIONAL
        assert saved.selected_existing_commitment_id is None
        assert saved.proposed_repayment == Decimal("100.01")
        assert saved.protected_monthly_buffer == Decimal("200.00")
        assert saved.basis_monthly_headroom == Decimal("1424.75")
        assert saved.scenario_headroom == Decimal("1324.74")
        assert saved.result_code.value == "appears_manageable_from_the_information_provided"
        assert saved.calculation_policy_version == "scenario-policy-v1"
        assert saved.created_at == SAVED_AT
        assert saved.basis_is_superseded is False
        assert get_effective_snapshot(db_session, customer_id=customer.id) == original_basis
        assert (
            get_editable_statement(
                db_session, customer_id=customer.id, statement_period=PERIOD
            ).version
            == original_statement.version
        )

    def test_change_existing_records_the_selected_commitment_and_uses_its_stored_amount(
        self, db_session
    ):
        customer, snapshot = confirmed_basis(db_session)
        commitment = next(
            entry for entry in snapshot.outgoing_entries if entry.entry_key == "commitment-1"
        )

        saved = save_additional(
            db_session,
            customer,
            snapshot,
            mode=ScenarioMode.CHANGE_EXISTING,
            selected_existing_commitment_id=commitment.id,
            proposed_repayment=Decimal("125.25"),
        )
        db_session.commit()

        assert saved.selected_existing_commitment_id == commitment.id
        assert saved.selected_existing_commitment_description == "Credit card repayment"
        assert saved.replaced_repayment == Decimal("75.25")
        assert saved.scenario_headroom == Decimal("1374.75")

    def test_decimal_pennies_and_policy_version_round_trip_through_postgresql(self, db_session):
        customer, snapshot = confirmed_basis(db_session)
        saved = save_additional(db_session, customer, snapshot)
        db_session.commit()
        db_session.expire_all()

        retrieved = get_repayment_scenario(
            db_session, customer_id=customer.id, scenario_id=saved.id
        )

        assert retrieved.proposed_repayment == Decimal("100.01")
        assert retrieved.scenario_headroom == Decimal("1324.74")
        assert retrieved.calculation_policy_version == "scenario-policy-v1"


class TestIdempotencyAndAtomicity:
    def test_retrying_the_same_save_returns_the_original_without_duplication(self, db_session):
        customer, snapshot = confirmed_basis(db_session)
        original = save_additional(db_session, customer, snapshot)
        db_session.commit()

        retried = save_additional(db_session, customer, snapshot)
        db_session.commit()

        assert retried.id == original.id
        assert db_session.scalar(select(func.count()).select_from(RepaymentScenario)) == 1

    def test_reusing_the_key_for_a_different_scenario_is_a_conflict(self, db_session):
        customer, snapshot = confirmed_basis(db_session)
        save_additional(db_session, customer, snapshot)
        db_session.commit()

        with pytest.raises(IdempotencyConflict):
            save_additional(
                db_session,
                customer,
                snapshot,
                proposed_repayment=Decimal("101.01"),
            )
        db_session.rollback()

        assert db_session.scalar(select(func.count()).select_from(RepaymentScenario)) == 1

    def test_a_failed_save_leaves_no_partial_scenario(self, db_session):
        customer, snapshot = confirmed_basis(db_session)

        with pytest.raises(ScenarioNotFound):
            save_additional(
                db_session,
                customer,
                snapshot,
                mode=ScenarioMode.CHANGE_EXISTING,
                selected_existing_commitment_id=None,
            )
        db_session.rollback()

        assert db_session.scalar(select(func.count()).select_from(RepaymentScenario)) == 0


class TestOwnershipAndImmutableBasis:
    def test_another_customer_cannot_save_list_or_retrieve_the_scenario(self, db_session):
        owner, snapshot = confirmed_basis(db_session)
        stranger = create_customer(db_session)
        saved = save_additional(db_session, owner, snapshot)
        db_session.commit()

        with pytest.raises(ScenarioNotFound):
            save_additional(db_session, stranger, snapshot, idempotency_key="stranger-save")
        assert list_repayment_scenarios(db_session, customer_id=stranger.id) == ()
        with pytest.raises(ScenarioNotFound):
            get_repayment_scenario(db_session, customer_id=stranger.id, scenario_id=saved.id)

    def test_a_later_correction_marks_the_basis_superseded_without_recalculation(self, db_session):
        customer, snapshot = confirmed_basis(db_session)
        saved = save_additional(db_session, customer, snapshot)
        db_session.commit()

        corrected = validate_statement(statement_payload(rent="1100.00"))
        classifications = {
            entry.entry_id: classify_outgoing(entry.description, preferences=())
            for entry in (*corrected.outgoing_entries, *corrected.repayment_commitments)
        }
        correct_snapshot(
            db_session,
            customer_id=customer.id,
            supersedes_snapshot_id=snapshot.id,
            statement=corrected,
            classifications=classifications,
            correction_reason="I corrected the rent amount.",
            idempotency_key="correct-basis",
            confirmed_at=datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc),
        )
        db_session.commit()

        retrieved = get_repayment_scenario(
            db_session, customer_id=customer.id, scenario_id=saved.id
        )
        assert retrieved.basis_is_superseded is True
        assert retrieved.basis_monthly_headroom == Decimal("1424.75")
        assert retrieved.scenario_headroom == Decimal("1324.74")

        with pytest.raises(ScenarioBasisNotCurrent):
            save_additional(
                db_session,
                customer,
                snapshot,
                idempotency_key="new-save-on-stale-basis",
            )
