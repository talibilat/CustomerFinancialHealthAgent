from customer_financial_health_api.providers.openai_client import build_shared_openai_client
from customer_financial_health_api.settings import Settings


def test_one_client_is_configured_for_both_azure_deployments():
    settings = Settings(
        _env_file=None,
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_classification_deployment="classify-v1",
        azure_openai_guidance_deployment="guidance-v2",
        azure_openai_auth_mode="api_key",
        azure_openai_api_key="not-a-real-key",
        azure_openai_timeout_seconds=10,
        azure_openai_max_retries=1,
        azure_openai_store=False,
    )

    configured = build_shared_openai_client(settings)

    assert configured is not None
    assert str(configured.client.base_url) == "https://example.openai.azure.com/openai/v1/"
    assert configured.client.timeout == 10
    assert configured.client.max_retries == 1
    assert configured.classification_deployment == "classify-v1"
    assert configured.guidance_deployment == "guidance-v2"


def test_an_unconfigured_provider_returns_no_client():
    settings = Settings(_env_file=None)

    assert build_shared_openai_client(settings) is None
