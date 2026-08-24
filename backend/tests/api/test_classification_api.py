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


def submitted(statement, **overrides):
    body = {
        "statement_period": statement["statement_period"],
        "currency": statement["currency"],
        "income_entries": [_entry(e) for e in statement["income_entries"]],
        "outgoing_entries": [_entry(e) for e in statement["outgoing_entries"]],
        "repayment_commitments": [_entry(e) for e in statement["repayment_commitments"]],
        "resilience": statement["resilience"],
        "looking_ahead": {
            "irregular_costs": [_entry(e) for e in statement["looking_ahead"]["irregular_costs"]],
            "protected_future_provisions": [
                _entry(e) for e in statement["looking_ahead"]["protected_future_provisions"]
            ],
            "expected_changes": [
                {
                    "entry_id": c["entry_id"],
                    "description": c["description"],
                    "kind": c["kind"],
                    "amount": c["original_amount"],
                    "frequency": c["original_frequency"],
                }
                for c in statement["looking_ahead"]["expected_changes"]
            ],
        },
    }
    body.update(overrides)
    return body


def retrieve(client):
    return client.get(f"/financial-statement?statement_period={PERIOD}").json()


def outgoing_named(statement, description):
    return next(e for e in statement["outgoing_entries"] if e["description"] == description)


class TestClassificationOnRetrieve:
    def test_a_known_outgoing_is_classified_deterministically(self, seeded):
        rent = outgoing_named(retrieve(seeded)["statement"], "Rent")

        assert rent["classification"]["display_category"] == "housing"
        assert rent["classification"]["outgoing_treatment"] == "protected_outgoing"
        assert rent["classification"]["source"] == "deterministic_rule"
        assert rent["classification"]["requires_confirmation"] is False

    def test_income_carries_no_classification(self, seeded):
        wages = retrieve(seeded)["statement"]["income_entries"][0]

        assert wages["classification"] is None

    def test_an_ambiguous_outgoing_requires_confirmation_and_offers_no_guess(self, seeded):
        statement = retrieve(seeded)["statement"]
        body = submitted(statement, expected_version=retrieve(seeded)["version"])
        body["outgoing_entries"].append(
            {"entry_id": "amb-1", "description": "Apple", "amount": "9.99", "frequency": "monthly"}
        )
        assert seeded.put("/financial-statement", json=body).status_code == 200

        apple = outgoing_named(retrieve(seeded)["statement"], "Apple")

        assert apple["classification"]["requires_confirmation"] is True
        assert apple["classification"]["reason_code"] == "description_ambiguous"
        assert apple["classification"]["display_category"] is None
        assert apple["classification"]["outgoing_treatment"] is None

    def test_an_unknown_outgoing_exposes_a_provider_proposal_without_confirming_it(self, seeded):
        from customer_financial_health_api.api.app import app
        from customer_financial_health_api.api.dependencies import get_classification_provider

        class ProviderFake:
            def suggest(self, **kwargs):
                return {
                    "display_category": "leisure_and_hobbies",
                    "outgoing_treatment": "flexible_living_cost",
                    "confidence": "0.82",
                    "reason": "Usually a hobby.",
                    "requires_clarification": False,
                }

        ordinary_fallback = app.dependency_overrides[get_classification_provider]
        app.dependency_overrides[get_classification_provider] = ProviderFake
        try:
            current = retrieve(seeded)
            body = submitted(current["statement"], expected_version=current["version"])
            body["outgoing_entries"].append(
                {
                    "entry_id": "unknown-1",
                    "description": "Dance class",
                    "amount": "25.00",
                    "frequency": "monthly",
                }
            )

            response = seeded.put("/financial-statement", json=body)
        finally:
            app.dependency_overrides[get_classification_provider] = ordinary_fallback

        assert response.status_code == 200
        dance_class = outgoing_named(response.json()["statement"], "Dance class")
        classification = dance_class["classification"]
        assert classification["display_category"] is None
        assert classification["source"] is None
        assert classification["requires_confirmation"] is True
        assert classification["suggestion"] == {
            "display_category": "leisure_and_hobbies",
            "outgoing_treatment": "flexible_living_cost",
            "confidence": "0.82",
            "reason": "Usually a hobby.",
            "requires_clarification": False,
        }

    def test_provider_generation_does_not_hold_a_database_transaction_open(
        self, seeded, db_session
    ):
        from customer_financial_health_api.api.dependencies import (
            get_classification_provider,
            get_db,
        )

        current = retrieve(seeded)
        body = submitted(current["statement"])
        body["outgoing_entries"].append(
            {
                "entry_id": "unknown-transaction-boundary",
                "description": "Dance class",
                "amount": "25.00",
                "frequency": "monthly",
            }
        )
        transaction_states: list[bool] = []

        class ProviderFake:
            def suggest(self, **kwargs):
                transaction_states.append(db_session.in_transaction())
                return None

        def same_session():
            yield db_session

        seeded.app.dependency_overrides[get_db] = same_session
        seeded.app.dependency_overrides[get_classification_provider] = ProviderFake
        try:
            response = seeded.post("/financial-statement/preview", json=body)
        finally:
            seeded.app.dependency_overrides.pop(get_db, None)
            seeded.app.dependency_overrides[get_classification_provider] = lambda: None

        assert response.status_code == 200
        assert transaction_states == [False]

    def test_retrieval_provider_does_not_hold_a_database_transaction_open(
        self, seeded, db_session
    ):
        from customer_financial_health_api.api.dependencies import (
            get_classification_provider,
            get_db,
        )

        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"].append(
            {
                "entry_id": "unknown-retrieval-boundary",
                "description": "Dance class",
                "amount": "25.00",
                "frequency": "monthly",
            }
        )
        assert seeded.put("/financial-statement", json=body).status_code == 200

        transaction_states: list[bool] = []

        class ProviderFake:
            def suggest(self, **kwargs):
                transaction_states.append(db_session.in_transaction())
                return None

        def same_session():
            yield db_session

        seeded.app.dependency_overrides[get_db] = same_session
        seeded.app.dependency_overrides[get_classification_provider] = ProviderFake
        try:
            response = retrieve(seeded)
        finally:
            seeded.app.dependency_overrides.pop(get_db, None)
            seeded.app.dependency_overrides[get_classification_provider] = lambda: None

        assert response["statement"]["outgoing_entries"][-1]["description"] == "Dance class"
        assert transaction_states == [False]

    def test_update_provider_does_not_hold_a_database_transaction_open(
        self, seeded, db_session
    ):
        from customer_financial_health_api.api.dependencies import (
            get_classification_provider,
            get_db,
        )

        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"].append(
            {
                "entry_id": "unknown-update-boundary",
                "description": "Dance class",
                "amount": "25.00",
                "frequency": "monthly",
            }
        )
        transaction_states: list[bool] = []

        class ProviderFake:
            def suggest(self, **kwargs):
                transaction_states.append(db_session.in_transaction())
                return None

        def same_session():
            yield db_session

        seeded.app.dependency_overrides[get_db] = same_session
        seeded.app.dependency_overrides[get_classification_provider] = ProviderFake
        try:
            response = seeded.put("/financial-statement", json=body)
        finally:
            seeded.app.dependency_overrides.pop(get_db, None)
            seeded.app.dependency_overrides[get_classification_provider] = lambda: None

        assert response.status_code == 200
        assert transaction_states == [False]


class TestConfirmationAndCorrection:
    def _add_ambiguous(self, client):
        current = retrieve(client)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"].append(
            {"entry_id": "amb-1", "description": "Apple", "amount": "9.99", "frequency": "monthly"}
        )
        assert client.put("/financial-statement", json=body).status_code == 200

    def test_confirming_records_category_treatment_source_and_taxonomy_version(self, seeded):
        self._add_ambiguous(seeded)
        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        for entry in body["outgoing_entries"]:
            if entry["description"] == "Apple":
                entry["classification"] = {
                    "display_category": "leisure_and_hobbies",
                    "outgoing_treatment": "flexible_living_cost",
                }

        assert seeded.put("/financial-statement", json=body).status_code == 200

        apple = outgoing_named(retrieve(seeded)["statement"], "Apple")
        assert apple["classification"]["display_category"] == "leisure_and_hobbies"
        assert apple["classification"]["outgoing_treatment"] == "flexible_living_cost"
        assert apple["classification"]["source"] == "customer_confirmation"
        assert apple["classification"]["taxonomy_version"] == "outgoing-taxonomy-v1"
        assert apple["classification"]["requires_confirmation"] is False

    def test_remembering_a_correction_classifies_the_same_phrase_next_time(self, seeded):
        self._add_ambiguous(seeded)
        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        for entry in body["outgoing_entries"]:
            if entry["description"] == "Apple":
                entry["classification"] = {
                    "display_category": "leisure_and_hobbies",
                    "outgoing_treatment": "flexible_living_cost",
                    "remember": True,
                }
        assert seeded.put("/financial-statement", json=body).status_code == 200

        # A brand-new entry with the same phrase now resolves from the preference.
        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"].append(
            {"entry_id": "amb-2", "description": "apple", "amount": "4.99", "frequency": "monthly"}
        )
        assert seeded.put("/financial-statement", json=body).status_code == 200

        second = next(
            e for e in retrieve(seeded)["statement"]["outgoing_entries"] if e["entry_id"] == "amb-2"
        )
        assert second["classification"]["display_category"] == "leisure_and_hobbies"
        assert second["classification"]["source"] == "customer_preference"

    def test_a_preference_overrides_the_global_rule_without_changing_it(self, seeded):
        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        for entry in body["outgoing_entries"]:
            if entry["description"] == "Rent":
                entry["classification"] = {
                    "display_category": "other",
                    "outgoing_treatment": "flexible_living_cost",
                    "remember": True,
                }
        assert seeded.put("/financial-statement", json=body).status_code == 200

        rent = outgoing_named(retrieve(seeded)["statement"], "Rent")
        assert rent["classification"]["display_category"] == "other"
        assert rent["classification"]["source"] in {"customer_preference", "customer_confirmation"}

    def test_an_unsupported_category_is_rejected_against_its_field(self, seeded):
        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"][0]["classification"] = {
            "display_category": "crypto_speculation",
            "outgoing_treatment": "flexible_living_cost",
        }

        response = seeded.put("/financial-statement", json=body)

        assert response.status_code == 422
        fields = [e["field"] for e in response.json()["detail"]["errors"]]
        assert "outgoing_entries.0.classification.display_category" in fields

    def test_an_unsupported_treatment_is_rejected_against_its_field(self, seeded):
        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"][0]["classification"] = {
            "display_category": "housing",
            "outgoing_treatment": "disposable_spending",
        }

        response = seeded.put("/financial-statement", json=body)

        assert response.status_code == 422
        fields = [e["field"] for e in response.json()["detail"]["errors"]]
        assert "outgoing_entries.0.classification.outgoing_treatment" in fields


class TestPreviewReportsUnresolved:
    def test_preview_names_every_unresolved_outgoing_and_withholds_confirmation(self, seeded):
        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"].append(
            {"entry_id": "amb-1", "description": "Apple", "amount": "9.99", "frequency": "monthly"}
        )
        seeded.put("/financial-statement", json=body)

        preview = seeded.post(
            "/financial-statement/preview", json=submitted(retrieve(seeded)["statement"])
        ).json()

        assert preview["unresolved_classifications"] == ["amb-1"]
        assert preview["can_confirm"] is False

    def test_a_fully_classified_statement_may_be_confirmed(self, seeded):
        preview = seeded.post(
            "/financial-statement/preview", json=submitted(retrieve(seeded)["statement"])
        ).json()

        assert preview["unresolved_classifications"] == []
        assert preview["can_confirm"] is True

    def test_an_unresolved_classification_never_changes_the_arithmetic(self, seeded):
        before = seeded.post(
            "/financial-statement/preview", json=submitted(retrieve(seeded)["statement"])
        ).json()

        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        seeded.put("/financial-statement", json=body)
        after = seeded.post(
            "/financial-statement/preview", json=submitted(retrieve(seeded)["statement"])
        ).json()

        assert after["monthly_headroom"] == before["monthly_headroom"]


class TestConfirmedClassificationsSurviveEditing:
    def _confirm_apple(self, client):
        current = retrieve(client)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"].append(
            {"entry_id": "amb-1", "description": "Apple", "amount": "9.99", "frequency": "monthly"}
        )
        client.put("/financial-statement", json=body)

        current = retrieve(client)
        body = submitted(current["statement"], expected_version=current["version"])
        for entry in body["outgoing_entries"]:
            if entry["entry_id"] == "amb-1":
                entry["classification"] = {
                    "display_category": "leisure_and_hobbies",
                    "outgoing_treatment": "flexible_living_cost",
                }
        assert client.put("/financial-statement", json=body).status_code == 200

    def test_a_later_save_that_omits_the_classification_does_not_discard_it(self, seeded):
        self._confirm_apple(seeded)

        # An ordinary edit elsewhere, with no classification restated.
        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        body["outgoing_entries"][0]["amount"] = "960.00"
        assert seeded.put("/financial-statement", json=body).status_code == 200

        apple = outgoing_named(retrieve(seeded)["statement"], "Apple")
        assert apple["classification"]["display_category"] == "leisure_and_hobbies"
        assert apple["classification"]["requires_confirmation"] is False

    def test_renaming_an_entry_retires_the_classification_it_no_longer_describes(self, seeded):
        self._confirm_apple(seeded)

        current = retrieve(seeded)
        body = submitted(current["statement"], expected_version=current["version"])
        for entry in body["outgoing_entries"]:
            if entry["entry_id"] == "amb-1":
                entry["description"] = "Dance class"
        assert seeded.put("/financial-statement", json=body).status_code == 200

        renamed = next(
            e for e in retrieve(seeded)["statement"]["outgoing_entries"] if e["entry_id"] == "amb-1"
        )
        # The customer confirmed what "Apple" was, not what "Dance class" is.
        assert renamed["classification"]["requires_confirmation"] is True
        assert renamed["classification"]["display_category"] is None
