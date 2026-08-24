"""Create the one OpenAI SDK client shared by bounded Azure operations."""

from dataclasses import dataclass

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from customer_financial_health_api.settings import Settings

AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass(frozen=True)
class SharedOpenAIClient:
    client: OpenAI
    classification_deployment: str | None
    guidance_deployment: str | None


def _configured(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.startswith("your-") or "YOUR-RESOURCE-NAME" in stripped:
        return None
    return stripped


def optional_capability_status(settings: Settings) -> dict[str, str]:
    endpoint = _configured(settings.azure_openai_endpoint)
    if settings.azure_openai_auth_mode == "entra_id":
        has_credentials = True
    else:
        has_credentials = bool(
            settings.azure_openai_api_key
            and settings.azure_openai_api_key.get_secret_value().strip()
        )
    base_configured = endpoint is not None and has_credentials
    return {
        "classification_suggestions": (
            "configured"
            if base_configured
            and _configured(settings.azure_openai_classification_deployment) is not None
            else "not_configured"
        ),
        "personalized_guidance": (
            "configured"
            if base_configured
            and _configured(settings.azure_openai_guidance_deployment) is not None
            else "not_configured"
        ),
    }


def build_shared_openai_client(settings: Settings) -> SharedOpenAIClient | None:
    """Return a configured Azure v1 client, or disable the optional capability."""
    endpoint = _configured(settings.azure_openai_endpoint)
    classification = _configured(settings.azure_openai_classification_deployment)
    guidance = _configured(settings.azure_openai_guidance_deployment)
    if endpoint is None or (classification is None and guidance is None):
        return None

    if settings.azure_openai_auth_mode == "api_key":
        if settings.azure_openai_api_key is None:
            return None
        api_key = settings.azure_openai_api_key.get_secret_value().strip()
        if not api_key:
            return None
        credential: str | object = api_key
    else:
        identity = DefaultAzureCredential(
            managed_identity_client_id=settings.azure_client_id or None
        )
        credential = get_bearer_token_provider(identity, AZURE_OPENAI_SCOPE)

    client = OpenAI(
        api_key=credential,
        base_url=f"{endpoint.rstrip('/')}/openai/v1/",
        timeout=float(settings.azure_openai_timeout_seconds),
        max_retries=int(settings.azure_openai_max_retries),
    )
    return SharedOpenAIClient(
        client=client,
        classification_deployment=classification,
        guidance_deployment=guidance,
    )
