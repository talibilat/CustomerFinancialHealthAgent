
import pytest

from customer_financial_health_api.persistence.seed import seed_demo_data

PERIOD = "2026-08-01"


@pytest.fixture()
def seeded(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    return client


def submitted(statement, **overrides):
    """Turn a retrieved statement into a submission body."""
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


def _entry(entry):
    return {
        "entry_id": entry["entry_id"],
        "description": entry["description"],
        "amount": entry["original_amount"],
        "frequency": entry["original_frequency"],
    }


class TestRetrieve:
    def test_retrieving_the_editable_statement_returns_a_closed_schema(self, seeded):
        response = seeded.get(f"/financial-statement?statement_period={PERIOD}")

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"version", "updated_at", "statement"}
        assert set(body["statement"].keys()) == {
            "statement_period",
            "currency",
            "income_entries",
            "outgoing_entries",
            "repayment_commitments",
            "resilience",
            "looking_ahead",
        }
        assert body["version"] == 1

    def test_original_amounts_and_frequencies_appear_beside_normalized_values(self, seeded):
        body = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        food = body["statement"]["outgoing_entries"][1]

        assert set(food.keys()) == {
            "entry_id",
            "description",
            "original_amount",
            "original_frequency",
            "normalized_monthly_amount",
            "classification",
        }
        assert food["original_amount"] == "120.00"
        assert food["original_frequency"] == "weekly"
        assert food["normalized_monthly_amount"] == "520.00"

    def test_unknown_statement_period_is_not_found(self, seeded):
        assert seeded.get("/financial-statement?statement_period=2020-01-01").status_code == 404


class TestPreview:
    def test_preview_recalculates_from_the_submitted_statement(self, seeded):
        statement = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()["statement"]
        body = submitted(statement)
        body["income_entries"][0]["amount"] = "3000.00"

        response = seeded.post("/financial-statement/preview", json=body)

        assert response.status_code == 200
        preview = response.json()
        assert preview["normalized_monthly_income"] == "3000.00"
        assert preview["result_code"] == "surplus"
        assert preview["calculation_policy_version"] == "normalization-policy-v1"

    def test_preview_does_not_change_the_stored_statement_or_confirmed_history(self, seeded):
        before = seeded.get("/overview").json()
        statement = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(statement["statement"])
        body["income_entries"][0]["amount"] = "9000.00"

        seeded.post("/financial-statement/preview", json=body)

        after_statement = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        assert after_statement["version"] == statement["version"]
        assert after_statement["statement"]["income_entries"][0]["original_amount"] == "2450.00"
        assert seeded.get("/overview").json() == before

    def test_preview_reports_resilience_separately_from_monthly_cash_flow(self, seeded):
        statement = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()["statement"]

        preview = seeded.post("/financial-statement/preview", json=submitted(statement)).json()

        # 2450.00 - (950.00 + 520.00 + 48.75)
        assert preview["resilience"]["result_code"] == "below_reserve"
        assert preview["monthly_headroom"] == "931.25"


class TestUpdate:
    def test_updating_advances_the_version_and_stores_the_change(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"], expected_version=retrieved["version"])
        body["outgoing_entries"].append(
            {"entry_id": "new-1", "description": "Gym", "amount": "30.00", "frequency": "monthly"}
        )

        response = seeded.put("/financial-statement", json=body)

        assert response.status_code == 200
        assert response.json()["version"] == 2

        stored = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        assert stored["version"] == 2
        assert stored["statement"]["outgoing_entries"][-1]["description"] == "Gym"

    def test_removing_an_entry_is_stored(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"], expected_version=retrieved["version"])
        del body["outgoing_entries"][0]

        seeded.put("/financial-statement", json=body)

        stored = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        assert len(stored["statement"]["outgoing_entries"]) == 2

    def test_updating_does_not_change_confirmed_history(self, seeded):
        before = seeded.get("/overview").json()
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"], expected_version=retrieved["version"])
        body["income_entries"][0]["amount"] = "10.00"

        seeded.put("/financial-statement", json=body)

        assert seeded.get("/overview").json() == before

    def test_a_stale_version_is_refused_with_a_conflict_that_allows_a_refresh(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"], expected_version=retrieved["version"])
        seeded.put("/financial-statement", json=body)

        # A second submission built from the now-stale version.
        response = seeded.put("/financial-statement", json=body)

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "statement_version_conflict"
        assert detail["current_version"] == 2


class TestFieldSpecificErrors:
    def test_invalid_submission_reports_every_bad_field_and_saves_nothing(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"], expected_version=retrieved["version"])
        body["income_entries"][0]["amount"] = "-5.00"
        body["outgoing_entries"][0]["amount"] = "NaN"
        body["outgoing_entries"][1]["frequency"] = "biweekly"

        response = seeded.put("/financial-statement", json=body)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "statement_invalid"
        assert [error["field"] for error in detail["errors"]] == [
            "income_entries.0.amount",
            "outgoing_entries.0.amount",
            "outgoing_entries.1.frequency",
        ]
        assert all(error["message"] for error in detail["errors"])

        unchanged = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        assert unchanged["version"] == retrieved["version"]
        assert unchanged["statement"]["income_entries"][0]["original_amount"] == "2450.00"

    @pytest.mark.parametrize(
        "amount", ["", "   ", "NaN", "Infinity", "-1.00", "1.005", "1000000.00", "abc"]
    )
    def test_unusable_amounts_are_rejected_against_their_field(self, seeded, amount):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"])
        body["income_entries"][0]["amount"] = amount

        response = seeded.post("/financial-statement/preview", json=body)

        assert response.status_code == 422
        assert response.json()["detail"]["errors"][0]["field"] == "income_entries.0.amount"

    def test_currency_other_than_gbp_is_rejected(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"], currency="USD")

        response = seeded.post("/financial-statement/preview", json=body)

        assert response.status_code == 422
        assert response.json()["detail"]["errors"][0]["field"] == "currency"


class TestClosedSchemas:
    @pytest.mark.parametrize(
        "field",
        ["customer_id", "monthly_headroom", "result_code", "version", "confirmed_at"],
    )
    def test_authority_bearing_and_calculated_fields_are_rejected(self, seeded, field):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"])
        body[field] = "injected"

        response = seeded.post("/financial-statement/preview", json=body)

        assert response.status_code == 422

    def test_unknown_field_inside_an_entry_is_rejected(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"])
        body["income_entries"][0]["normalized_monthly_amount"] = "99999.00"

        response = seeded.post("/financial-statement/preview", json=body)

        assert response.status_code == 422

    def test_malformed_json_is_a_stable_client_error(self, seeded):
        response = seeded.post(
            "/financial-statement/preview",
            content="{not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422
        assert "Traceback" not in response.text


class TestLookingAhead:
    def test_annual_irregular_cost_previews_as_a_monthly_provision_without_moving_headroom(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        baseline = seeded.post(
            "/financial-statement/preview", json=submitted(retrieved["statement"])
        ).json()

        body = submitted(retrieved["statement"])
        body["looking_ahead"]["irregular_costs"].append(
            {
                "entry_id": "a1",
                "description": "Car insurance",
                "amount": "600.00",
                "frequency": "annual",
            }
        )

        preview = seeded.post("/financial-statement/preview", json=body).json()

        assert preview["normalized_monthly_irregular_costs"] == "50.00"
        assert preview["monthly_headroom"] == baseline["monthly_headroom"]

    def test_omitted_looking_ahead_information_is_reported_as_a_limitation(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()

        preview = seeded.post(
            "/financial-statement/preview", json=submitted(retrieved["statement"])
        ).json()

        assert "looking_ahead_info_missing" in preview["warnings"]

    def test_expected_change_is_stored_and_previewed_without_altering_this_period(self, seeded):
        retrieved = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        body = submitted(retrieved["statement"], expected_version=retrieved["version"])
        body["looking_ahead"]["expected_changes"].append(
            {
                "entry_id": "e1",
                "description": "Shift reduction",
                "kind": "income_decrease",
                "amount": "200.00",
                "frequency": "monthly",
            }
        )

        assert seeded.put("/financial-statement", json=body).status_code == 200

        stored = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()
        change = stored["statement"]["looking_ahead"]["expected_changes"][0]
        assert change["kind"] == "income_decrease"
        assert change["original_amount"] == "200.00"

        preview = seeded.post(
            "/financial-statement/preview", json=submitted(stored["statement"])
        ).json()
        assert preview["normalized_monthly_income"] == "2450.00"


def test_statement_response_does_not_expose_customer_identifiers_as_authority(seeded):
    body = seeded.get(f"/financial-statement?statement_period={PERIOD}").json()

    assert "customer_id" not in body
    assert "customer_id" not in body["statement"]
