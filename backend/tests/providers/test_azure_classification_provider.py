import json
import logging
from types import SimpleNamespace

from customer_financial_health_api.providers.azure_openai import (
    AzureClassificationOutput,
    AzureClassificationSuggestionProvider,
    logger as provider_logger,
)


class RecordingResponses:
    def __init__(self, output, *, status="completed", response_output=None):
        self.output = output
        self.status = status
        self.response_output = response_output or []
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            status=self.status,
            output_parsed=self.output,
            output=self.response_output,
            _request_id="azure-request-1",
        )


class FakeOpenAIClient:
    def __init__(self, output, **response_options):
        self.responses = RecordingResponses(output, **response_options)


def test_the_adapter_makes_one_minimal_stateless_structured_request():
    client = FakeOpenAIClient(
        AzureClassificationOutput(
            display_category="leisure_and_hobbies",
            outgoing_treatment="flexible_living_cost",
            confidence="0.82",
            reason="Usually a hobby.",
            requires_clarification=False,
        )
    )
    provider = AzureClassificationSuggestionProvider(
        client=client,
        deployment="classification-deployment",
    )

    suggestion = provider.suggest(
        description="dance class",
        allowed_categories=("housing", "leisure_and_hobbies"),
        allowed_treatments=("protected_outgoing", "flexible_living_cost"),
    )

    assert suggestion == {
        "display_category": "leisure_and_hobbies",
        "outgoing_treatment": "flexible_living_cost",
        "confidence": "0.82",
        "reason": "Usually a hobby.",
        "requires_clarification": False,
    }
    assert len(client.responses.calls) == 1
    request = client.responses.calls[0]
    assert request["model"] == "classification-deployment"
    assert request["text_format"] is AzureClassificationOutput
    assert request["store"] is False
    assert "previous_response_id" not in request
    assert "tools" not in request
    assert len(request["input"]) == 2
    supplied = json.loads(request["input"][1]["content"])
    assert supplied == {
        "description": "dance class",
        "allowed_categories": ["housing", "leisure_and_hobbies"],
        "allowed_treatments": ["protected_outgoing", "flexible_living_cost"],
    }
    assert "customer" not in supplied
    assert "£" not in request["input"][1]["content"]


def test_an_incomplete_response_is_not_exposed_as_a_suggestion(caplog):
    provider_logger.disabled = False
    caplog.set_level(logging.INFO)
    client = FakeOpenAIClient(
        AzureClassificationOutput(
            display_category="leisure_and_hobbies",
            outgoing_treatment="flexible_living_cost",
            confidence="0.82",
            reason="Usually a hobby.",
            requires_clarification=False,
        ),
        status="incomplete",
    )
    provider = AzureClassificationSuggestionProvider(client=client, deployment="classify-v1")

    suggestion = provider.suggest(
        description="private dance class",
        allowed_categories=("leisure_and_hobbies",),
        allowed_treatments=("flexible_living_cost",),
    )

    assert suggestion is None
    record = caplog.records[-1]
    assert record.operation == "classification_suggestion"
    assert record.outcome == "fallback"
    assert record.fallback_reason == "incomplete"
    assert record.deployment == "classify-v1"
    assert record.azure_request_id == "azure-request-1"
    assert "private dance class" not in caplog.text


def test_a_refusal_is_not_exposed_as_a_suggestion():
    refusal = SimpleNamespace(
        type="message",
        content=[SimpleNamespace(type="refusal", refusal="provider detail")],
    )
    client = FakeOpenAIClient(None, response_output=[refusal])
    provider = AzureClassificationSuggestionProvider(client=client, deployment="classify-v1")

    suggestion = provider.suggest(
        description="dance class",
        allowed_categories=("leisure_and_hobbies",),
        allowed_treatments=("flexible_living_cost",),
    )

    assert suggestion is None
