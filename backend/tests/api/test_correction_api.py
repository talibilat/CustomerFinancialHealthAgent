import uuid

import pytest

from customer_financial_health_api.persistence.seed import seed_demo_data

PERIOD = "2026-08-01"
REASON = "I entered the wrong rent amount."


@pytest.fixture()
def seeded(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    return client


def _entry(e, **kw):
    body = {
        "entry_id": e["entry_id"],
        "description": e["description"],
        "amount": e["original_amount"],
        "frequency": e["original_frequency"],
    }
    body.update(kw)
    return body


def statement_body(client, rent=None):
    current = client.get(f"/financial-statement?statement_period={PERIOD}").json()
    s = current["statement"]
    outs = [_entry(e) for e in s["outgoing_entries"]]
    if rent is not None:
        outs[0]["amount"] = rent
    return {
        "statement_period": s["statement_period"],
        "currency": s["currency"],
        "income_entries": [_entry(e) for e in s["income_entries"]],
        "outgoing_entries": outs,
        "repayment_commitments": [_entry(e) for e in s["repayment_commitments"]],
        "resilience": s["resilience"],
        "looking_ahead": {
            "irregular_costs": [],
            "protected_future_provisions": [],
            "expected_changes": [],
        },
    }


def effective_snapshot_id(client):
    return client.get("/history").json()["series"][0]["snapshot_id"]


def correct(client, snapshot_id, body, key="fix-1"):
    return client.post(
        f"/history/{snapshot_id}/correct", json=body, headers={"Idempotency-Key": key}
    )


def correction_body(client, rent="1100.00", reason=REASON):
    return {**statement_body(client, rent=rent), "correction_reason": reason}


class TestCorrecting:
    def test_a_correction_supersedes_the_original_and_keeps_its_period(self, seeded):
        original_id = effective_snapshot_id(seeded)

        response = correct(seeded, original_id, correction_body(seeded))

        assert response.status_code == 201
        body = response.json()
        assert body["statement_period"] == PERIOD
        assert body["supersedes_snapshot_id"] == original_id
        assert body["correction_reason"] == REASON

    def test_history_shows_the_correction_as_effective_and_keeps_the_original(self, seeded):
        original_id = effective_snapshot_id(seeded)
        correct(seeded, original_id, correction_body(seeded))

        history = seeded.get("/history").json()

        assert history["total"] == 2
        assert len(history["series"]) == 1
        assert history["series"][0]["snapshot_id"] != original_id
        assert original_id in [s["snapshot_id"] for s in history["snapshots"]]

    def test_the_original_remains_readable_with_its_own_values(self, seeded):
        original_id = effective_snapshot_id(seeded)
        correct(seeded, original_id, correction_body(seeded))

        original = next(
            s
            for s in seeded.get("/history").json()["snapshots"]
            if s["snapshot_id"] == original_id
        )

        assert original["monthly_headroom"] == "931.25"
        assert original["outgoing_entries"][0]["original_amount"] == "950.00"


class TestReasonValidation:
    @pytest.mark.parametrize("reason", ["", "   "])
    def test_a_blank_reason_is_refused_against_its_field(self, seeded, reason):
        response = correct(
            seeded, effective_snapshot_id(seeded), correction_body(seeded, reason=reason)
        )

        assert response.status_code == 422
        fields = [e["field"] for e in response.json()["detail"]["errors"]]
        assert "correction_reason" in fields

    def test_an_over_long_reason_is_refused(self, seeded):
        response = correct(
            seeded, effective_snapshot_id(seeded), correction_body(seeded, reason="x" * 501)
        )

        assert response.status_code == 422


class TestConflicts:
    def test_correcting_an_already_corrected_snapshot_is_a_conflict(self, seeded):
        original_id = effective_snapshot_id(seeded)
        correct(seeded, original_id, correction_body(seeded))

        response = correct(seeded, original_id, correction_body(seeded, rent="1200.00"), key="fix-2")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "snapshot_already_superseded"

    def test_repeating_a_correction_returns_the_same_snapshot(self, seeded):
        original_id = effective_snapshot_id(seeded)
        body = correction_body(seeded)

        first = correct(seeded, original_id, body)
        second = correct(seeded, original_id, body)

        assert second.json()["snapshot_id"] == first.json()["snapshot_id"]
        assert seeded.get("/history").json()["total"] == 2

    def test_reusing_a_key_for_a_different_correction_is_a_conflict(self, seeded):
        original_id = effective_snapshot_id(seeded)
        correct(seeded, original_id, correction_body(seeded))

        response = correct(seeded, original_id, correction_body(seeded, rent="1300.00"))

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "idempotency_key_conflict"


class TestNonEnumeratingErrors:
    def test_an_unknown_snapshot_is_not_found_without_disclosing_anything(self, seeded):
        response = correct(seeded, str(uuid.uuid4()), correction_body(seeded))

        assert response.status_code == 404
        assert response.json()["detail"] == "snapshot_not_found"

    def test_another_customers_snapshot_looks_exactly_like_a_missing_one(self, seeded, db_session):
        from customer_financial_health_api.domain.classification import classify_outgoing
        from customer_financial_health_api.domain.statement import validate_statement
        from customer_financial_health_api.persistence.repository import (
            confirm_statement,
            create_customer,
            save_editable_statement,
        )
        from datetime import date, datetime, timezone

        stranger = create_customer(db_session)
        stranger_statement = validate_statement(
            {
                "statement_period": "2026-08-01",
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
            db_session, customer_id=stranger.id, statement=stranger_statement, expected_version=None
        )
        db_session.commit()
        theirs = confirm_statement(
            db_session,
            customer_id=stranger.id,
            statement=stranger_statement,
            classifications={"o1": classify_outgoing("Rent", preferences=())},
            expected_version=saved.version,
            idempotency_key="stranger-1",
            confirmed_at=datetime(2026, 8, 2, 9, 0, tzinfo=timezone.utc),
        )
        db_session.commit()

        unknown = correct(seeded, str(uuid.uuid4()), correction_body(seeded), key="a")
        theirs_response = correct(seeded, str(theirs.id), correction_body(seeded), key="b")

        # Identical responses: ownership cannot be probed by identifier.
        assert theirs_response.status_code == unknown.status_code == 404
        assert theirs_response.json() == unknown.json()
