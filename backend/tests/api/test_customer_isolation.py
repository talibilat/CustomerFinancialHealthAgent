"""Every identifier-bearing endpoint must answer identically for a stranger's
record and a record that never existed. Otherwise ownership is discoverable by
trying identifiers, which is the whole point of object-level authorization.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.repayment import ScenarioMode
from customer_financial_health_api.domain.statement import StatementEntry, validate_statement
from customer_financial_health_api.persistence.repository import (
    confirm_statement,
    create_customer,
    save_editable_statement,
    save_repayment_scenario,
)
from customer_financial_health_api.persistence.seed import seed_demo_data

PERIOD = "2026-08-01"
UNKNOWN = str(uuid.UUID(int=0))


@pytest.fixture()
def seeded(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    return client


@pytest.fixture()
def stranger(db_session):
    """A second customer with a confirmed snapshot and a saved scenario."""
    other = create_customer(db_session)
    statement = validate_statement(
        {
            "statement_period": PERIOD,
            "income_entries": [
                {"entry_id": "i1", "description": "Wages", "amount": "1000.00", "frequency": "monthly"}
            ],
            "outgoing_entries": [
                {"entry_id": "o1", "description": "Rent", "amount": "400.00", "frequency": "monthly"}
            ],
            "repayment_commitments": [],
        }
    )
    saved = save_editable_statement(
        db_session, customer_id=other.id, statement=statement, expected_version=None
    )
    db_session.commit()
    snapshot = confirm_statement(
        db_session,
        customer_id=other.id,
        statement=statement,
        classifications={"o1": classify_outgoing("Rent", preferences=())},
        expected_version=saved.version,
        idempotency_key="stranger-confirm",
        confirmed_at=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    scenario = save_repayment_scenario(
        db_session,
        customer_id=other.id,
        basis_snapshot_id=snapshot.id,
        mode=ScenarioMode.ADDITIONAL,
        selected_existing_commitment_id=None,
        proposed_repayment=Decimal("50.00"),
        protected_monthly_buffer=None,
        idempotency_key="stranger-scenario",
        created_at=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
    )
    db_session.commit()

    return {"customer_id": other.id, "snapshot_id": str(snapshot.id), "scenario_id": str(scenario.id)}


def correction_body(client):
    current = client.get(f"/financial-statement?statement_period={PERIOD}").json()
    s = current["statement"]

    def entry(e):
        return {
            "entry_id": e["entry_id"],
            "description": e["description"],
            "amount": e["original_amount"],
            "frequency": e["original_frequency"],
        }

    return {
        "statement_period": s["statement_period"],
        "currency": s["currency"],
        "correction_reason": "Probing another customer's record.",
        "income_entries": [entry(e) for e in s["income_entries"]],
        "outgoing_entries": [entry(e) for e in s["outgoing_entries"]],
        "repayment_commitments": [entry(e) for e in s["repayment_commitments"]],
        "resilience": s["resilience"],
        "looking_ahead": {
            "irregular_costs": [],
            "protected_future_provisions": [],
            "expected_changes": [],
        },
    }


class TestReadsAreNonEnumerating:
    def test_a_strangers_saved_scenario_looks_exactly_like_a_missing_one(self, seeded, stranger):
        theirs = seeded.get(f"/repayment-scenarios/{stranger['scenario_id']}")
        unknown = seeded.get(f"/repayment-scenarios/{UNKNOWN}")

        assert theirs.status_code == unknown.status_code
        assert theirs.json() == unknown.json()

    def test_listing_scenarios_never_includes_another_customers(self, seeded, stranger):
        listed = seeded.get("/repayment-scenarios").json()

        ids = {s["scenario_id"] for s in listed.get("scenarios", listed if isinstance(listed, list) else [])}
        assert stranger["scenario_id"] not in ids

    def test_history_never_includes_another_customers_snapshots(self, seeded, stranger):
        history = seeded.get("/history").json()

        ids = {s["snapshot_id"] for s in history["snapshots"]}
        assert stranger["snapshot_id"] not in ids


class TestMutationsAreRejectedBeforeAnyWrite:
    def test_correcting_a_strangers_snapshot_matches_an_unknown_identifier(self, seeded, stranger):
        body = correction_body(seeded)

        theirs = seeded.post(
            f"/history/{stranger['snapshot_id']}/correct",
            json=body,
            headers={"Idempotency-Key": "probe-a"},
        )
        unknown = seeded.post(
            f"/history/{UNKNOWN}/correct", json=body, headers={"Idempotency-Key": "probe-b"}
        )

        assert theirs.status_code == unknown.status_code
        assert theirs.json() == unknown.json()

    def test_a_rejected_cross_customer_correction_changes_neither_customer(
        self, seeded, stranger, db_session
    ):
        from customer_financial_health_api.persistence.models import ConfirmedSnapshot

        before = {
            str(s.id): (s.monthly_headroom, s.supersedes_snapshot_id)
            for s in db_session.execute(
                __import__("sqlalchemy").select(ConfirmedSnapshot)
            ).scalars()
        }

        seeded.post(
            f"/history/{stranger['snapshot_id']}/correct",
            json=correction_body(seeded),
            headers={"Idempotency-Key": "probe-c"},
        )

        db_session.expire_all()
        after = {
            str(s.id): (s.monthly_headroom, s.supersedes_snapshot_id)
            for s in db_session.execute(
                __import__("sqlalchemy").select(ConfirmedSnapshot)
            ).scalars()
        }
        assert after == before


class TestGuessableIdentifiersDoNotHelp:
    @pytest.mark.parametrize(
        "candidate",
        [
            "00000000-0000-0000-0000-000000000001",
            "11111111-1111-1111-1111-111111111111",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
        ],
    )
    def test_probing_sequential_identifiers_reveals_nothing(self, seeded, stranger, candidate):
        probed = seeded.get(f"/repayment-scenarios/{candidate}")
        unknown = seeded.get(f"/repayment-scenarios/{UNKNOWN}")

        assert probed.status_code == unknown.status_code
        assert probed.json() == unknown.json()

    def test_a_malformed_identifier_does_not_leak_a_different_shape(self, seeded):
        malformed = seeded.get("/repayment-scenarios/not-a-uuid")

        assert malformed.status_code in {404, 422}
        assert "Traceback" not in malformed.text
