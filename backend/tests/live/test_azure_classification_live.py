import os

import pytest

from customer_financial_health_api.domain.suggest import classify_with_suggestions
from customer_financial_health_api.providers.azure_openai import (
    AzureClassificationSuggestionProvider,
)
from customer_financial_health_api.providers.openai_client import build_shared_openai_client
from customer_financial_health_api.settings import Settings

pytestmark = pytest.mark.live


def test_configured_azure_returns_an_unconfirmed_allow_listed_suggestion():
    if os.environ.get("RUN_LIVE_AZURE_OPENAI_TESTS") != "1":
        pytest.skip("set RUN_LIVE_AZURE_OPENAI_TESTS=1 to call Azure OpenAI")

    configured = build_shared_openai_client(Settings(_env_file=None))
    if configured is None or configured.classification_deployment is None:
        pytest.skip("Azure classification configuration is incomplete")

    provider = AzureClassificationSuggestionProvider(
        client=configured.client,
        deployment=configured.classification_deployment,
    )

    outcome = classify_with_suggestions("dance class", provider=provider)

    assert outcome.suggestion is not None
    assert outcome.requires_confirmation
    assert not outcome.is_resolved
    assert outcome.source is None
