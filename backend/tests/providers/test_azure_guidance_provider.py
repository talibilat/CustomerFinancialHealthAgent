from decimal import Decimal
from types import SimpleNamespace

import pytest

from customer_financial_health_api.domain.guidance import GuidanceFacts
from customer_financial_health_api.providers.azure_guidance import (
    AzureGuidanceGenerator,
    AzureGuidanceOutput,
)


class FakeResponses:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None

    def parse(self, **kwargs):
        self.request = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, responses):
        self.responses = responses


def facts():
    return GuidanceFacts(
        normalized_monthly_income=Decimal("2450.00"),
        normalized_monthly_outgoings=Decimal("1950.00"),
        monthly_headroom=Decimal("500.00"),
        result_code="surplus",
        warning_codes=(),
        support_codes=(),
    )


def completed():
    parsed = AzureGuidanceOutput(
        text="Your reported figures leave £500.00 of monthly headroom.",
        result_code="surplus",
        warning_codes=[],
        support_codes=[],
        referenced_fact_keys=["monthly_headroom"],
    )
    return SimpleNamespace(
        status="completed", output=[], output_parsed=parsed, _request_id="request-1"
    )


def test_guidance_uses_the_shared_stateless_responses_contract():
    responses = FakeResponses(completed())
    provider = AzureGuidanceGenerator(client=FakeClient(responses), deployment="guidance-v1")

    result = provider.generate(facts())

    assert result["result_code"] == "surplus"
    assert responses.request["model"] == "guidance-v1"
    assert responses.request["text_format"] is AzureGuidanceOutput
    assert responses.request["store"] is False
    assert "previous_response_id" not in responses.request
    supplied = responses.request["input"][1]["content"]
    assert "customer_id" not in supplied
    assert "snapshot_id" not in supplied
    assert "line_items" not in supplied


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(status="incomplete", output=[], output_parsed=None),
        SimpleNamespace(
            status="completed",
            output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
            output_parsed=None,
        ),
        SimpleNamespace(status="completed", output=[], output_parsed=None),
    ],
)
def test_incomplete_refused_or_empty_provider_output_returns_no_candidate(response):
    provider = AzureGuidanceGenerator(
        client=FakeClient(FakeResponses(response)), deployment="guidance-v1"
    )

    assert provider.generate(facts()) is None


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timeout"),
        RuntimeError("rate_limited"),
        RuntimeError("content_filter"),
        ValueError("malformed_schema"),
        RuntimeError("provider_failure"),
    ],
)
def test_provider_failures_are_raised_for_the_guidance_fallback(error):
    provider = AzureGuidanceGenerator(
        client=FakeClient(FakeResponses(error=error)), deployment="guidance-v1"
    )

    with pytest.raises(type(error)):
        provider.generate(facts())
