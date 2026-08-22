from datetime import date
from decimal import Decimal

import pytest

from customer_financial_health_api.domain.statement import (
    StatementValidationError,
    preview_statement,
    validate_statement,
)


def minimal_payload(**overrides):
    payload = {
        "statement_period": "2026-08-01",
        "income_entries": [
            {"entry_id": "i1", "description": "Wages", "amount": "2450.00", "frequency": "monthly"}
        ],
        "outgoing_entries": [
            {"entry_id": "o1", "description": "Rent", "amount": "950.00", "frequency": "monthly"}
        ],
        "repayment_commitments": [],
    }
    payload.update(overrides)
    return payload


class TestValidStatements:
    def test_valid_statement_preserves_original_amounts_and_frequencies(self):
        statement = validate_statement(minimal_payload())

        assert statement.statement_period == date(2026, 8, 1)
        assert statement.income_entries[0].amount == Decimal("2450.00")
        assert statement.income_entries[0].frequency.value == "monthly"
        assert statement.outgoing_entries[0].description == "Rent"

    def test_preview_reports_monthly_headroom_from_the_submitted_statement(self):
        preview = preview_statement(validate_statement(minimal_payload()))

        assert preview.position.normalized_monthly_income == Decimal("2450.00")
        assert preview.position.normalized_monthly_outgoings == Decimal("950.00")
        assert preview.position.monthly_headroom == Decimal("1500.00")
        assert preview.position.result_code.value == "surplus"

    def test_existing_repayment_commitments_count_as_outgoings_and_report_separately(self):
        preview = preview_statement(
            validate_statement(
                minimal_payload(
                    repayment_commitments=[
                        {
                            "entry_id": "r1",
                            "description": "Credit card",
                            "amount": "120.00",
                            "frequency": "monthly",
                        }
                    ]
                )
            )
        )

        assert preview.position.normalized_monthly_outgoings == Decimal("1070.00")
        assert preview.position.monthly_headroom == Decimal("1380.00")
        assert preview.normalized_monthly_repayment_commitments == Decimal("120.00")


class TestFieldSpecificErrors:
    @pytest.mark.parametrize(
        "amount",
        ["-0.01", "", "   ", "NaN", "Infinity", "-Infinity", "1,200.00", "abc", "1.005"],
    )
    def test_unusable_amount_is_rejected_against_its_own_field(self, amount):
        payload = minimal_payload()
        payload["income_entries"][0]["amount"] = amount

        with pytest.raises(StatementValidationError) as raised:
            validate_statement(payload)

        assert [error.field for error in raised.value.errors] == ["income_entries.0.amount"]

    def test_unknown_frequency_is_rejected_against_its_own_field(self):
        payload = minimal_payload()
        payload["outgoing_entries"][0]["frequency"] = "biweekly"

        with pytest.raises(StatementValidationError) as raised:
            validate_statement(payload)

        assert [error.field for error in raised.value.errors] == ["outgoing_entries.0.frequency"]

    def test_every_invalid_field_is_reported_not_just_the_first(self):
        payload = minimal_payload()
        payload["income_entries"][0]["amount"] = "-5.00"
        payload["outgoing_entries"][0]["amount"] = "NaN"
        payload["outgoing_entries"][0]["frequency"] = "biweekly"

        with pytest.raises(StatementValidationError) as raised:
            validate_statement(payload)

        assert [error.field for error in raised.value.errors] == [
            "income_entries.0.amount",
            "outgoing_entries.0.amount",
            "outgoing_entries.0.frequency",
        ]

    def test_amount_above_the_supported_maximum_is_rejected_before_persistence(self):
        payload = minimal_payload()
        payload["income_entries"][0]["amount"] = "1000000.00"

        with pytest.raises(StatementValidationError) as raised:
            validate_statement(payload)

        assert raised.value.errors[0].field == "income_entries.0.amount"
        assert raised.value.errors[0].code == "amount_above_maximum"

    def test_currency_other_than_gbp_is_rejected(self):
        with pytest.raises(StatementValidationError) as raised:
            validate_statement(minimal_payload(currency="USD"))

        assert [error.field for error in raised.value.errors] == ["currency"]
        assert raised.value.errors[0].code == "currency_not_supported"


class TestBoundaryAmounts:
    def test_zero_and_one_penny_amounts_are_accepted_exactly(self):
        payload = minimal_payload()
        payload["income_entries"][0]["amount"] = "0.00"
        payload["outgoing_entries"][0]["amount"] = "0.01"

        preview = preview_statement(validate_statement(payload))

        assert preview.position.normalized_monthly_income == Decimal("0.00")
        assert preview.position.monthly_headroom == Decimal("-0.01")
        assert preview.position.result_code.value == "shortfall"
        assert "zero_income" in preview.position.warnings

    def test_largest_supported_amount_is_accepted(self):
        payload = minimal_payload()
        payload["income_entries"][0]["amount"] = "999999.99"

        preview = preview_statement(validate_statement(payload))

        assert preview.position.normalized_monthly_income == Decimal("999999.99")

    @pytest.mark.parametrize(
        ("frequency", "expected"),
        [
            ("weekly", Decimal("433.33")),
            ("fortnightly", Decimal("216.67")),
            ("four_weekly", Decimal("108.33")),
            ("monthly", Decimal("100.00")),
            ("quarterly", Decimal("33.33")),
            ("annual", Decimal("8.33")),
        ],
    )
    def test_every_supported_frequency_normalizes_through_the_versioned_policy(self, frequency, expected):
        payload = minimal_payload()
        payload["income_entries"][0]["amount"] = "100.00"
        payload["income_entries"][0]["frequency"] = frequency

        preview = preview_statement(validate_statement(payload))

        assert preview.position.normalized_monthly_income == expected


class TestResilienceSection:
    def test_resilience_information_is_optional_and_previews_when_supplied(self):
        preview = preview_statement(
            validate_statement(
                minimal_payload(
                    resilience={
                        "accessible_savings": "300.00",
                        "protected_reserve": "1000.00",
                        "current_account_balance": "-45.30",
                    }
                )
            )
        )

        assert preview.resilience.result_code.value == "below_reserve"
        assert preview.resilience.reserve_gap == Decimal("700.00")
        assert preview.resilience.current_account_balance == Decimal("-45.30")
        # Resilience never moves monthly cash flow.
        assert preview.position.monthly_headroom == Decimal("1500.00")

    def test_omitted_resilience_creates_a_limitation_rather_than_a_default(self):
        preview = preview_statement(validate_statement(minimal_payload()))

        assert preview.resilience.result_code is None
        assert "resilience_info_missing" in preview.resilience.warnings
        assert preview.resilience.accessible_savings is None

    def test_negative_savings_is_rejected_against_its_own_field(self):
        with pytest.raises(StatementValidationError) as raised:
            validate_statement(minimal_payload(resilience={"accessible_savings": "-1.00"}))

        assert [error.field for error in raised.value.errors] == ["resilience.accessible_savings"]
        assert raised.value.errors[0].code == "amount_negative"

    def test_overdraft_is_accepted_as_a_negative_current_account_balance(self):
        statement = validate_statement(minimal_payload(resilience={"current_account_balance": "-250.00"}))

        assert statement.resilience.current_account_balance == Decimal("-250.00")


class TestLookingAheadSection:
    def test_annual_irregular_cost_becomes_a_monthly_provision_without_changing_headroom(self):
        preview = preview_statement(
            validate_statement(
                minimal_payload(
                    looking_ahead={
                        "irregular_costs": [
                            {
                                "entry_id": "a1",
                                "description": "Car insurance",
                                "amount": "600.00",
                                "frequency": "annual",
                            }
                        ]
                    }
                )
            )
        )

        assert preview.normalized_monthly_irregular_costs == Decimal("50.00")
        assert preview.position.monthly_headroom == Decimal("1500.00")

    def test_protected_future_provisions_report_separately_from_outgoings(self):
        preview = preview_statement(
            validate_statement(
                minimal_payload(
                    looking_ahead={
                        "protected_future_provisions": [
                            {
                                "entry_id": "p1",
                                "description": "Emergency fund",
                                "amount": "25.00",
                                "frequency": "monthly",
                            }
                        ]
                    }
                )
            )
        )

        assert preview.normalized_monthly_protected_future_provisions == Decimal("25.00")
        assert preview.position.normalized_monthly_outgoings == Decimal("950.00")

    def test_expected_change_is_reported_without_altering_the_current_period(self):
        preview = preview_statement(
            validate_statement(
                minimal_payload(
                    looking_ahead={
                        "expected_changes": [
                            {
                                "entry_id": "e1",
                                "description": "Shift reduction",
                                "kind": "income_decrease",
                                "amount": "200.00",
                                "frequency": "monthly",
                            }
                        ]
                    }
                )
            )
        )

        assert preview.expected_changes[0].kind.value == "income_decrease"
        assert preview.position.normalized_monthly_income == Decimal("2450.00")
        assert preview.position.monthly_headroom == Decimal("1500.00")

    def test_omitted_looking_ahead_information_creates_a_limitation(self):
        preview = preview_statement(validate_statement(minimal_payload()))

        assert "looking_ahead_info_missing" in preview.warnings

    def test_irregular_cost_repeating_an_outgoing_is_flagged_for_review_not_counted_twice(self):
        preview = preview_statement(
            validate_statement(
                minimal_payload(
                    looking_ahead={
                        "irregular_costs": [
                            {
                                "entry_id": "a1",
                                "description": "rent",
                                "amount": "600.00",
                                "frequency": "annual",
                            }
                        ]
                    }
                )
            )
        )

        assert "possible_irregular_cost_duplication" in preview.warnings
        assert preview.position.normalized_monthly_outgoings == Decimal("950.00")

    def test_unsupported_expected_change_kind_is_rejected_against_its_own_field(self):
        with pytest.raises(StatementValidationError) as raised:
            validate_statement(
                minimal_payload(
                    looking_ahead={
                        "expected_changes": [
                            {
                                "entry_id": "e1",
                                "description": "Bonus",
                                "kind": "lottery_win",
                                "amount": "10.00",
                                "frequency": "monthly",
                            }
                        ]
                    }
                )
            )

        assert [error.field for error in raised.value.errors] == ["looking_ahead.expected_changes.0.kind"]


class TestInvariants:
    def test_a_higher_outgoing_cannot_improve_monthly_headroom(self):
        smaller = preview_statement(validate_statement(minimal_payload()))

        payload = minimal_payload()
        payload["outgoing_entries"][0]["amount"] = "951.00"
        larger = preview_statement(validate_statement(payload))

        assert larger.position.monthly_headroom < smaller.position.monthly_headroom

    def test_accessible_savings_never_become_monthly_income(self):
        without = preview_statement(validate_statement(minimal_payload()))
        with_savings = preview_statement(
            validate_statement(
                minimal_payload(
                    resilience={"accessible_savings": "5000.00", "protected_reserve": "0.00"}
                )
            )
        )

        assert with_savings.position.normalized_monthly_income == without.position.normalized_monthly_income
        assert with_savings.position.monthly_headroom == without.position.monthly_headroom
