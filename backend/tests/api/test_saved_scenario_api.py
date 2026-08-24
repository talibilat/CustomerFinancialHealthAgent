import uuid
from datetime import datetime, timezone

from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.statement import FinancialStatement, validate_statement
from customer_financial_health_api.persistence.repository import (
    confirm_statement,
    correct_snapshot,
    create_customer,
    get_demo_customer,
    get_effective_snapshot,
    save_editable_statement,
)
from customer_financial_health_api.persistence.seed import (
    INCOME_ENTRIES,
    OUTGOING_ENTRIES,
    REPAYMENT_COMMITMENTS,
    STATEMENT_PERIOD,
    seed_demo_data,
)


def save_body(basis_snapshot_id: str, **overrides):
    body = {
        "basis_snapshot_id": basis_snapshot_id,
        "mode": "additional",
        "proposed_repayment": "100.01",
        "protected_monthly_buffer": "200.00",
    }
    body.update(overrides)
    return body


def seeded_basis(db_session):
    seed_demo_data(db_session)
    db_session.commit()
    customer = get_demo_customer(db_session)
    snapshot = get_effective_snapshot(db_session, customer_id=customer.id)
    return customer, snapshot


def basis_with_commitment(db_session):
    customer = create_customer(db_session)
    statement = validate_statement(
        {
            "statement_period": "2026-08-01",
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
                    "amount": "950.00",
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
    )
    classifications = {
        entry.entry_id: classify_outgoing(entry.description, preferences=())
        for entry in (*statement.outgoing_entries, *statement.repayment_commitments)
    }
    editable = save_editable_statement(
        db_session,
        customer_id=customer.id,
        statement=statement,
        expected_version=None,
        classifications=classifications,
    )
    db_session.commit()
    snapshot = confirm_statement(
        db_session,
        customer_id=customer.id,
        statement=statement,
        classifications=classifications,
        expected_version=editable.version,
        idempotency_key="confirm-with-commitment",
        confirmed_at=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
    )
    db_session.commit()
    return customer, snapshot


def save(client, basis_id: str, *, key: str = "save-scenario-1", **overrides):
    return client.post(
        "/repayment-scenarios",
        json=save_body(basis_id, **overrides),
        headers={"Idempotency-Key": key},
    )


class TestSaveScenario:
    def test_save_is_explicit_and_returns_the_stored_comparison(self, client, db_session):
        _, basis = seeded_basis(db_session)

        response = save(client, str(basis.id))

        assert response.status_code == 201
        saved = response.json()
        assert saved["basis_snapshot_id"] == str(basis.id)
        assert saved["basis_statement_period"] == "2026-08-01"
        assert saved["basis_monthly_headroom"] == "931.25"
        assert saved["proposed_repayment"] == "100.01"
        assert saved["scenario_headroom"] == "831.24"
        assert saved["calculation_policy_version"] == "scenario-policy-v1"
        assert saved["basis_is_superseded"] is False

    def test_same_key_and_body_returns_the_original_without_duplication(self, client, db_session):
        _, basis = seeded_basis(db_session)

        first = save(client, str(basis.id)).json()
        retried = save(client, str(basis.id)).json()
        listed = client.get("/repayment-scenarios").json()

        assert retried["id"] == first["id"]
        assert listed["total"] == 1

    def test_same_key_with_a_different_body_is_a_conflict(self, client, db_session):
        _, basis = seeded_basis(db_session)
        save(client, str(basis.id))

        response = save(client, str(basis.id), proposed_repayment="125.00")

        assert response.status_code == 409
        assert response.json()["detail"] == "idempotency_key_conflict"

    def test_calculated_and_authority_fields_are_rejected(self, client, db_session):
        _, basis = seeded_basis(db_session)

        response = save(client, str(basis.id), scenario_headroom="999999.00")

        assert response.status_code == 422

    def test_change_existing_uses_the_selected_commitment_from_the_owned_basis(
        self, client, db_session
    ):
        _, basis = basis_with_commitment(db_session)
        basis_response = client.get("/repayment-scenario/basis")

        assert basis_response.status_code == 200
        commitment = basis_response.json()["existing_repayment_commitments"][0]
        response = save(
            client,
            str(basis.id),
            mode="change_existing",
            selected_existing_commitment_id=commitment["id"],
            proposed_repayment="125.25",
        )

        assert response.status_code == 201
        saved = response.json()
        assert saved["selected_existing_commitment_id"] == commitment["id"]
        assert saved["selected_existing_commitment_description"] == "Credit card repayment"
        assert saved["replaced_repayment"] == "75.25"
        assert saved["scenario_headroom"] == "1374.75"


class TestOwnershipAndSafeResources:
    def test_unknown_basis_is_a_safe_not_found(self, client, db_session):
        seeded_basis(db_session)

        response = save(client, str(uuid.uuid4()))

        assert response.status_code == 404
        assert response.json()["detail"] == "resource_not_found"

    def test_another_customers_basis_is_indistinguishable_from_unknown(
        self, client, db_session
    ):
        seeded_basis(db_session)
        stranger = create_customer(db_session)
        statement = FinancialStatement(
            statement_period=STATEMENT_PERIOD,
            income_entries=INCOME_ENTRIES,
            outgoing_entries=OUTGOING_ENTRIES,
            repayment_commitments=REPAYMENT_COMMITMENTS,
        )
        classifications = {
            entry.entry_id: classify_outgoing(entry.description, preferences=())
            for entry in (*statement.outgoing_entries, *statement.repayment_commitments)
        }
        editable = save_editable_statement(
            db_session,
            customer_id=stranger.id,
            statement=statement,
            expected_version=None,
            classifications=classifications,
        )
        db_session.commit()
        other_basis = confirm_statement(
            db_session,
            customer_id=stranger.id,
            statement=statement,
            classifications=classifications,
            expected_version=editable.version,
            idempotency_key="stranger-confirm",
            confirmed_at=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        )
        db_session.commit()

        response = save(client, str(other_basis.id), key="cross-customer-save")

        assert response.status_code == 404
        assert response.json()["detail"] == "resource_not_found"

    def test_unknown_scenario_detail_is_a_safe_not_found(self, client, db_session):
        seeded_basis(db_session)

        response = client.get(f"/repayment-scenarios/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "resource_not_found"


class TestSavedBasisStatus:
    def test_list_and_detail_mark_a_later_superseded_basis_without_changing_values(
        self, client, db_session
    ):
        customer, basis = seeded_basis(db_session)
        saved = save(client, str(basis.id)).json()
        corrected = FinancialStatement(
            statement_period=STATEMENT_PERIOD,
            income_entries=INCOME_ENTRIES,
            outgoing_entries=OUTGOING_ENTRIES,
            repayment_commitments=REPAYMENT_COMMITMENTS,
        )
        classifications = {
            entry.entry_id: classify_outgoing(entry.description, preferences=())
            for entry in (*corrected.outgoing_entries, *corrected.repayment_commitments)
        }
        correct_snapshot(
            db_session,
            customer_id=customer.id,
            supersedes_snapshot_id=basis.id,
            statement=corrected,
            classifications=classifications,
            correction_reason="I corrected this statement.",
            idempotency_key="correct-after-scenario",
            confirmed_at=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
        )
        db_session.commit()

        listed = client.get("/repayment-scenarios").json()["scenarios"][0]
        detail = client.get(f"/repayment-scenarios/{saved['id']}").json()

        assert listed["basis_is_superseded"] is True
        assert detail["basis_is_superseded"] is True
        assert detail["basis_monthly_headroom"] == "931.25"
        assert detail["scenario_headroom"] == "831.24"

    def test_a_new_save_against_an_already_superseded_basis_is_stale(self, client, db_session):
        customer, basis = seeded_basis(db_session)
        corrected = FinancialStatement(
            statement_period=STATEMENT_PERIOD,
            income_entries=INCOME_ENTRIES,
            outgoing_entries=OUTGOING_ENTRIES,
            repayment_commitments=REPAYMENT_COMMITMENTS,
        )
        classifications = {
            entry.entry_id: classify_outgoing(entry.description, preferences=())
            for entry in (*corrected.outgoing_entries, *corrected.repayment_commitments)
        }
        correct_snapshot(
            db_session,
            customer_id=customer.id,
            supersedes_snapshot_id=basis.id,
            statement=corrected,
            classifications=classifications,
            correction_reason="I corrected this statement.",
            idempotency_key="correct-first",
            confirmed_at=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
        )
        db_session.commit()

        response = save(client, str(basis.id), key="stale-save")

        assert response.status_code == 409
        assert response.json()["detail"] == "basis_snapshot_superseded"
