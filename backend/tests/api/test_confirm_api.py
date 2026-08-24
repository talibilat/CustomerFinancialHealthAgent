import pytest

from customer_financial_health_api.persistence.seed import seed_demo_data

PERIOD = "2026-08-01"


@pytest.fixture()
def seeded(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    return client


def _entry(entry, **overrides):
    body = {
        "entry_id": entry["entry_id"],
        "description": entry["description"],
        "amount": entry["original_amount"],
        "frequency": entry["original_frequency"],
    }
    body.update(overrides)
    return body


def retrieve(client):
    return client.get(f"/financial-statement?statement_period={PERIOD}").json()


def confirmation_body(client, **overrides):
    current = retrieve(client)
    s = current["statement"]
    body = {
        "statement_period": s["statement_period"],
        "currency": s["currency"],
        "expected_version": current["version"],
        "income_entries": [_entry(e) for e in s["income_entries"]],
        "outgoing_entries": [_entry(e) for e in s["outgoing_entries"]],
        "repayment_commitments": [_entry(e) for e in s["repayment_commitments"]],
        "resilience": s["resilience"],
        "looking_ahead": {
            "irregular_costs": [],
            "protected_future_provisions": [],
            "expected_changes": [],
        },
        "checked_information": True,
    }
    body.update(overrides)
    return body


def confirm(client, body, key="key-1"):
    return client.post(
        "/financial-statement/confirm", json=body, headers={"Idempotency-Key": key}
    )


class TestSuccessfulConfirmation:
    def test_confirming_returns_the_new_snapshot_and_updates_the_overview(self, seeded):
        before = seeded.get("/overview").json()

        response = confirm(seeded, confirmation_body(seeded))

        assert response.status_code == 201
        body = response.json()
        assert body["monthly_headroom"] == "931.25"
        assert body["statement_period"] == PERIOD
        assert body["confirmed_at"].endswith("Z") or "+00:00" in body["confirmed_at"]

        after = seeded.get("/overview").json()
        assert after["confirmed_at"] != before["confirmed_at"]

    def test_the_response_never_exposes_a_customer_identifier_as_authority(self, seeded):
        body = confirm(seeded, confirmation_body(seeded)).json()

        assert "customer_id" not in body


class TestIdempotency:
    def test_repeating_the_request_returns_the_same_snapshot(self, seeded):
        body = confirmation_body(seeded)

        first = confirm(seeded, body)
        second = confirm(seeded, body)

        assert first.status_code == 201
        assert second.status_code in {200, 201}
        assert second.json()["snapshot_id"] == first.json()["snapshot_id"]

    def test_reusing_a_key_for_a_different_request_is_a_conflict(self, seeded):
        body = confirmation_body(seeded)
        confirm(seeded, body)

        different = dict(body)
        different["income_entries"] = [
            {**body["income_entries"][0], "amount": "9999.00"}
        ]
        response = confirm(seeded, different)

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "idempotency_key_conflict"

    def test_a_missing_idempotency_key_is_refused(self, seeded):
        response = seeded.post("/financial-statement/confirm", json=confirmation_body(seeded))

        assert response.status_code == 422


class TestRefusals:
    def test_a_stale_version_requires_a_fresh_preview(self, seeded):
        body = confirmation_body(seeded)
        confirm(seeded, body)

        response = confirm(seeded, body, key="key-2")

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "statement_version_conflict"

    def test_an_unresolved_classification_blocks_confirmation_and_names_it(self, seeded):
        current = retrieve(seeded)
        update = confirmation_body(seeded)
        update["outgoing_entries"].append(
            {"entry_id": "amb-1", "description": "Apple", "amount": "9.99", "frequency": "monthly"}
        )
        update.pop("checked_information")
        seeded.put("/financial-statement", json={**update, "expected_version": current["version"]})

        response = confirm(seeded, confirmation_body(seeded))

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "classifications_unresolved"
        assert detail["entry_ids"] == ["amb-1"]

    def test_confirmation_requires_the_customer_to_say_they_checked_the_information(self, seeded):
        response = confirm(seeded, confirmation_body(seeded, checked_information=False))

        assert response.status_code == 422
        fields = [e["field"] for e in response.json()["detail"]["errors"]]
        assert "checked_information" in fields

    def test_an_unusable_amount_is_still_refused_against_its_field(self, seeded):
        body = confirmation_body(seeded)
        body["income_entries"][0]["amount"] = "-1.00"

        response = confirm(seeded, body)

        assert response.status_code == 422
        assert response.json()["detail"]["errors"][0]["field"] == "income_entries.0.amount"

    def test_malformed_json_is_a_stable_client_error(self, seeded):
        response = seeded.post(
            "/financial-statement/confirm",
            content="{not json",
            headers={"Content-Type": "application/json", "Idempotency-Key": "key-9"},
        )

        assert response.status_code == 422
        assert "Traceback" not in response.text

    def test_provider_generation_does_not_hold_a_database_transaction_open(
        self, seeded, db_session
    ):
        from customer_financial_health_api.api.dependencies import (
            get_classification_provider,
            get_db,
        )

        current = retrieve(seeded)
        update = confirmation_body(seeded)
        update["outgoing_entries"].append(
            {
                "entry_id": "unknown-confirm-boundary",
                "description": "Dance class",
                "amount": "25.00",
                "frequency": "monthly",
            }
        )
        update.pop("checked_information")
        assert seeded.put(
            "/financial-statement",
            json={**update, "expected_version": current["version"]},
        ).status_code == 200

        transaction_states: list[bool] = []

        class ProviderFake:
            def suggest(self, **kwargs):
                transaction_states.append(db_session.in_transaction())
                return None

        def same_session():
            yield db_session

        body = confirmation_body(seeded)
        seeded.app.dependency_overrides[get_db] = same_session
        seeded.app.dependency_overrides[get_classification_provider] = ProviderFake
        try:
            response = confirm(seeded, body, key="provider-transaction-boundary")
        finally:
            seeded.app.dependency_overrides.pop(get_db, None)
            seeded.app.dependency_overrides[get_classification_provider] = lambda: None

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "classifications_unresolved"
        assert transaction_states == [False]


class TestHistoryIsPreserved:
    def test_confirming_never_edits_the_previous_snapshot(self, seeded):
        original = seeded.get("/overview").json()
        confirm(seeded, confirmation_body(seeded))

        # The seeded snapshot is still readable at its own figures.
        assert original["monthly_headroom"] == "931.25"

    def test_a_confirmed_statement_must_be_refreshed_before_editing_again(self, seeded):
        before = retrieve(seeded)["version"]
        confirm(seeded, confirmation_body(seeded))

        assert retrieve(seeded)["version"] == before + 1
