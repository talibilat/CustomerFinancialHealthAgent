import pytest

from customer_financial_health_api.persistence.seed import seed_demo_data


@pytest.fixture()
def seeded(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    return client


def body(**overrides):
    payload = {"mode": "additional", "proposed_repayment": "100.00"}
    payload.update(overrides)
    return payload


def explore(client, payload):
    return client.post("/repayment-scenario/preview", json=payload)


class TestBasis:
    def test_the_scenario_starts_from_the_effective_snapshot_and_names_it(self, seeded):
        response = explore(seeded, body())

        assert response.status_code == 200
        result = response.json()
        assert result["basis_monthly_headroom"] == "931.25"
        assert result["basis_snapshot_id"]
        assert result["basis_statement_period"] == "2026-08-01"

    def test_no_confirmed_snapshot_is_a_clear_state_not_a_crash(self, client, db_session):
        response = explore(client, body())

        assert response.status_code == 404
        assert response.json()["detail"] == "no_confirmed_snapshot"

    def test_exploring_never_changes_the_basis_or_the_statement(self, seeded):
        before_overview = seeded.get("/overview").json()
        before_history = seeded.get("/history").json()["total"]
        before_statement = seeded.get(
            "/financial-statement?statement_period=2026-08-01"
        ).json()["version"]

        explore(seeded, body(proposed_repayment="500.00"))

        assert seeded.get("/overview").json() == before_overview
        assert seeded.get("/history").json()["total"] == before_history
        assert (
            seeded.get("/financial-statement?statement_period=2026-08-01").json()["version"]
            == before_statement
        )


class TestArithmetic:
    def test_additional_mode_subtracts_once(self, seeded):
        result = explore(seeded, body(proposed_repayment="200.00")).json()

        assert result["scenario_headroom"] == "731.25"

    def test_change_existing_mode_frees_the_selected_commitment(self, seeded):
        result = explore(
            seeded,
            body(mode="change_existing", replaced_repayment="150.00", proposed_repayment="200.00"),
        ).json()

        # 931.25 + 150.00 - 200.00
        assert result["scenario_headroom"] == "881.25"

    def test_the_result_is_one_of_the_three_permitted_states(self, seeded):
        result = explore(seeded, body()).json()

        assert result["result_code"] in {
            "not_enough_reported_headroom",
            "may_leave_limited_room",
            "appears_manageable_from_the_information_provided",
        }

    def test_the_source_totals_and_policy_version_are_inspectable(self, seeded):
        result = explore(seeded, body()).json()

        assert result["calculation_policy_version"] == "scenario-policy-v1"
        assert result["basis_monthly_headroom"] == "931.25"
        assert result["proposed_repayment"] == "100.00"


class TestBufferHandling:
    def test_meeting_the_buffer_exactly_appears_manageable(self, seeded):
        result = explore(
            seeded, body(proposed_repayment="731.25", protected_monthly_buffer="200.00")
        ).json()

        assert result["scenario_headroom"] == "200.00"
        assert result["result_code"] == "appears_manageable_from_the_information_provided"

    def test_missing_the_buffer_by_a_penny_leaves_limited_room(self, seeded):
        result = explore(
            seeded, body(proposed_repayment="731.26", protected_monthly_buffer="200.00")
        ).json()

        assert result["result_code"] == "may_leave_limited_room"
        assert result["buffer_shortfall"] == "0.01"

    def test_an_omitted_buffer_is_a_limitation_not_an_invented_threshold(self, seeded):
        result = explore(seeded, body()).json()

        assert "protected_buffer_missing" in result["warnings"]
        assert result["result_code"] != "appears_manageable_from_the_information_provided"


class TestRejections:
    @pytest.mark.parametrize(
        "amount", ["-1.00", "0.00", "", "   ", "NaN", "Infinity", "abc", "1.005", "1000000.00"]
    )
    def test_an_unusable_repayment_is_refused_against_its_field(self, seeded, amount):
        response = explore(seeded, body(proposed_repayment=amount))

        assert response.status_code == 422
        assert response.json()["detail"]["errors"][0]["field"] == "proposed_repayment"

    def test_a_negative_buffer_is_refused_against_its_field(self, seeded):
        response = explore(seeded, body(protected_monthly_buffer="-1.00"))

        assert response.status_code == 422
        assert response.json()["detail"]["errors"][0]["field"] == "protected_monthly_buffer"

    def test_an_unknown_mode_is_refused_against_its_field(self, seeded):
        response = explore(seeded, body(mode="wipe_the_debt"))

        assert response.status_code == 422
        assert response.json()["detail"]["errors"][0]["field"] == "mode"

    def test_change_existing_without_a_commitment_is_refused(self, seeded):
        response = explore(seeded, body(mode="change_existing"))

        assert response.status_code == 422
        fields = [e["field"] for e in response.json()["detail"]["errors"]]
        assert "replaced_repayment" in fields

    @pytest.mark.parametrize(
        "field", ["customer_id", "scenario_headroom", "result_code", "basis_snapshot_id"]
    )
    def test_calculated_and_authority_bearing_fields_are_rejected(self, seeded, field):
        response = explore(seeded, {**body(), field: "injected"})

        assert response.status_code == 422

    def test_malformed_json_is_a_stable_client_error(self, seeded):
        response = seeded.post(
            "/repayment-scenario/preview",
            content="{not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422
        assert "Traceback" not in response.text


class TestSavingsNeverBecomeCapacity:
    def test_the_response_never_offers_savings_as_repayment_capacity(self, seeded):
        result = explore(seeded, body()).json()

        assert "accessible_savings" not in result
        assert "protected_reserve" not in result
