from decimal import Decimal

import pytest

from customer_financial_health_api.domain.repayment import (
    SCENARIO_POLICY_VERSION,
    ScenarioMode,
    ScenarioResultCode,
    calculate_scenario,
)

HEADROOM = Decimal("500.00")


def scenario(**kwargs):
    params = {
        "monthly_headroom": HEADROOM,
        "mode": ScenarioMode.ADDITIONAL,
        "proposed_repayment": Decimal("100.00"),
    }
    params.update(kwargs)
    return calculate_scenario(**params)


class TestAdditionalMode:
    def test_the_proposed_repayment_is_subtracted_exactly_once(self):
        result = scenario(proposed_repayment=Decimal("120.00"))

        assert result.scenario_headroom == Decimal("380.00")
        assert result.calculation_policy_version == SCENARIO_POLICY_VERSION

    def test_existing_commitments_are_untouched_in_additional_mode(self):
        result = scenario(proposed_repayment=Decimal("100.00"), replaced_repayment=None)

        # Nothing is removed; the basis headroom already contains every commitment.
        assert result.replaced_repayment is None
        assert result.scenario_headroom == Decimal("400.00")


class TestChangeExistingMode:
    def test_only_the_selected_commitment_is_removed_and_the_new_amount_added_once(self):
        result = scenario(
            mode=ScenarioMode.CHANGE_EXISTING,
            replaced_repayment=Decimal("75.00"),
            proposed_repayment=Decimal("120.00"),
        )

        # 500 + 75 - 120
        assert result.scenario_headroom == Decimal("455.00")
        assert result.replaced_repayment == Decimal("75.00")

    def test_replacing_with_a_smaller_amount_frees_headroom(self):
        result = scenario(
            mode=ScenarioMode.CHANGE_EXISTING,
            replaced_repayment=Decimal("200.00"),
            proposed_repayment=Decimal("50.00"),
        )

        assert result.scenario_headroom == Decimal("650.00")

    def test_change_existing_without_a_selected_commitment_is_refused(self):
        with pytest.raises(ValueError):
            scenario(mode=ScenarioMode.CHANGE_EXISTING, replaced_repayment=None)


class TestBoundaries:
    def test_a_scenario_that_exactly_exhausts_headroom_is_not_a_shortfall(self):
        result = scenario(proposed_repayment=Decimal("500.00"), protected_monthly_buffer=Decimal("0.00"))

        assert result.scenario_headroom == Decimal("0.00")
        assert result.result_code != ScenarioResultCode.NOT_ENOUGH_REPORTED_HEADROOM

    def test_a_one_penny_shortfall_is_not_enough_reported_headroom(self):
        result = scenario(proposed_repayment=Decimal("500.01"))

        assert result.scenario_headroom == Decimal("-0.01")
        assert result.result_code == ScenarioResultCode.NOT_ENOUGH_REPORTED_HEADROOM

    def test_meeting_the_buffer_exactly_is_inclusive_and_appears_manageable(self):
        result = scenario(
            proposed_repayment=Decimal("300.00"), protected_monthly_buffer=Decimal("200.00")
        )

        assert result.scenario_headroom == Decimal("200.00")
        assert result.result_code == ScenarioResultCode.APPEARS_MANAGEABLE

    def test_missing_the_buffer_by_one_penny_leaves_limited_room(self):
        result = scenario(
            proposed_repayment=Decimal("300.01"), protected_monthly_buffer=Decimal("200.00")
        )

        assert result.scenario_headroom == Decimal("199.99")
        assert result.result_code == ScenarioResultCode.MAY_LEAVE_LIMITED_ROOM
        assert result.buffer_shortfall == Decimal("0.01")


class TestMissingBuffer:
    def test_no_buffer_is_a_limitation_rather_than_an_invented_threshold(self):
        result = scenario(proposed_repayment=Decimal("100.00"), protected_monthly_buffer=None)

        assert result.result_code == ScenarioResultCode.MAY_LEAVE_LIMITED_ROOM
        assert "protected_buffer_missing" in result.warnings
        assert result.buffer_shortfall is None

    def test_a_comfortable_scenario_still_cannot_be_called_manageable_without_a_buffer(self):
        result = scenario(proposed_repayment=Decimal("1.00"), protected_monthly_buffer=None)

        assert result.result_code != ScenarioResultCode.APPEARS_MANAGEABLE


class TestRefusals:
    @pytest.mark.parametrize("amount", [Decimal("-0.01"), Decimal("-100.00")])
    def test_a_negative_repayment_is_refused(self, amount):
        with pytest.raises(ValueError):
            scenario(proposed_repayment=amount)

    def test_a_zero_repayment_is_not_a_meaningful_scenario(self):
        with pytest.raises(ValueError):
            scenario(proposed_repayment=Decimal("0.00"))

    def test_a_negative_protected_buffer_is_refused(self):
        with pytest.raises(ValueError):
            scenario(protected_monthly_buffer=Decimal("-1.00"))


class TestInvariants:
    def test_increasing_the_repayment_never_increases_scenario_headroom(self):
        amounts = [Decimal(a) for a in ("50.00", "100.00", "250.00", "499.99")]
        headrooms = [scenario(proposed_repayment=a).scenario_headroom for a in amounts]

        assert headrooms == sorted(headrooms, reverse=True)

    def test_the_result_never_improves_as_the_repayment_grows(self):
        severity = {
            ScenarioResultCode.APPEARS_MANAGEABLE: 0,
            ScenarioResultCode.MAY_LEAVE_LIMITED_ROOM: 1,
            ScenarioResultCode.NOT_ENOUGH_REPORTED_HEADROOM: 2,
        }
        buffer = Decimal("100.00")
        ranks = [
            severity[
                scenario(proposed_repayment=Decimal(a), protected_monthly_buffer=buffer).result_code
            ]
            for a in ("50.00", "300.00", "400.00", "450.00", "600.00")
        ]

        assert ranks == sorted(ranks)

    def test_the_scenario_depends_only_on_headroom_and_the_amounts(self):
        """Accessible savings can never become monthly repayment capacity."""
        import inspect

        parameters = set(inspect.signature(calculate_scenario).parameters)

        assert "accessible_savings" not in parameters
        assert "protected_reserve" not in parameters

    def test_a_shortfall_reports_exactly_how_much_is_missing(self):
        result = scenario(proposed_repayment=Decimal("620.00"))

        assert result.scenario_headroom == Decimal("-120.00")
        assert result.result_code == ScenarioResultCode.NOT_ENOUGH_REPORTED_HEADROOM


class TestBasisIsUnchanged:
    def test_the_basis_headroom_is_reported_alongside_the_scenario(self):
        result = scenario(proposed_repayment=Decimal("100.00"))

        assert result.basis_monthly_headroom == HEADROOM
        assert result.proposed_repayment == Decimal("100.00")


class TestFragileOutcomes:
    def test_leaving_nothing_at_all_is_flagged_even_when_the_buffer_is_met(self):
        """A zero buffer is the customer's choice, but zero left is still fragile."""
        result = scenario(
            proposed_repayment=Decimal("500.00"), protected_monthly_buffer=Decimal("0.00")
        )

        assert result.scenario_headroom == Decimal("0.00")
        assert result.result_code == ScenarioResultCode.APPEARS_MANAGEABLE
        assert "no_headroom_left_after_this_repayment" in result.warnings

    def test_a_scenario_that_leaves_something_is_not_flagged_that_way(self):
        result = scenario(
            proposed_repayment=Decimal("499.99"), protected_monthly_buffer=Decimal("0.00")
        )

        assert "no_headroom_left_after_this_repayment" not in result.warnings
