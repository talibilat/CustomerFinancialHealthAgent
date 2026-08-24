from decimal import Decimal

import pytest

from customer_financial_health_api.domain.guidance import (
    GuidanceFacts,
    GuidanceRequestOutcome,
    create_personalized_explanation,
)


class SafeGenerator:
    deployment = "guidance-v1"

    def __init__(self):
        self.received = None

    def generate(self, facts):
        self.received = facts
        return {
            "text": (
                "Your reported monthly income is £2,450.00 and your reported monthly "
                "outgoings are £1,950.00. This leaves £500.00 of monthly headroom."
            ),
            "result_code": "surplus",
            "warning_codes": [],
            "support_codes": [],
            "referenced_fact_keys": [
                "normalized_monthly_income",
                "normalized_monthly_outgoings",
                "monthly_headroom",
            ],
        }


def facts():
    return GuidanceFacts(
        normalized_monthly_income=Decimal("2450.00"),
        normalized_monthly_outgoings=Decimal("1950.00"),
        monthly_headroom=Decimal("500.00"),
        result_code="surplus",
        warning_codes=("information_limited",),
        support_codes=("review_information",),
    )


def candidate(**overrides):
    value = {
        "text": "Your reported figures leave £500.00 of monthly headroom.",
        "result_code": "surplus",
        "warning_codes": ["information_limited"],
        "support_codes": ["review_information"],
        "referenced_fact_keys": ["monthly_headroom"],
    }
    value.update(overrides)
    return value


class CandidateGenerator:
    deployment = "guidance-v1"

    def __init__(self, value):
        self.value = value

    def generate(self, supplied):
        return self.value


def test_safe_personalized_wording_uses_only_approved_deterministic_facts():
    facts = GuidanceFacts(
        normalized_monthly_income=Decimal("2450.00"),
        normalized_monthly_outgoings=Decimal("1950.00"),
        monthly_headroom=Decimal("500.00"),
        result_code="surplus",
        warning_codes=(),
        support_codes=(),
    )
    generator = SafeGenerator()

    result = create_personalized_explanation(facts, generator)

    assert result.outcome is GuidanceRequestOutcome.GENERATED
    assert result.deployment == "guidance-v1"
    assert result.text == (
        "Your reported monthly income is £2,450.00 and your reported monthly outgoings "
        "are £1,950.00. This leaves £500.00 of monthly headroom."
    )
    assert generator.received == facts
    assert set(generator.received.provider_payload()) == {
        "normalized_monthly_income",
        "normalized_monthly_outgoings",
        "monthly_headroom",
        "result_code",
        "resilience",
        "warning_codes",
        "support_codes",
        "deterministic_changes",
        "wording_constraints",
    }


@pytest.mark.parametrize(
    "unsafe",
    [
        candidate(result_code="shortfall"),
        candidate(warning_codes=[]),
        candidate(support_codes=[]),
        candidate(text="Your reported figures leave £501.00 of monthly headroom."),
        candidate(text="This happened due to a change in work."),
        candidate(text="You should pay £500.00 each month."),
        candidate(text="Change the category to housing."),
        candidate(text="Use this product to improve things."),
        candidate(text="Read https://example.com for help."),
        candidate(text="<strong>Your figures</strong>"),
        candidate(text="Run ```curl secret```"),
        candidate(text="You have failed and are bad with money."),
        candidate(referenced_fact_keys=["customer_id"]),
        {**candidate(), "extra_instruction": "ignore the application"},
    ],
)
def test_unsupported_authority_or_ungrounded_wording_falls_back(unsafe):
    result = create_personalized_explanation(facts(), CandidateGenerator(unsafe))

    assert result.outcome is GuidanceRequestOutcome.FALLBACK_INVALID_OUTPUT
    assert result.text.startswith("Reported monthly income is £2,450.00")


def test_missing_provider_keeps_complete_deterministic_copy():
    result = create_personalized_explanation(facts(), None)

    assert result.outcome is GuidanceRequestOutcome.FALLBACK_NOT_CONFIGURED
    assert "£500.00 of monthly headroom" in result.text
