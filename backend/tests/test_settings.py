import pytest
from pydantic import ValidationError

from customer_financial_health_api.settings import Settings


def test_the_documented_false_environment_value_starts_the_application(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_STORE", "false")

    settings = Settings(_env_file=None)

    assert settings.azure_openai_store is False


def test_response_storage_cannot_be_enabled(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_STORE", "true")

    with pytest.raises(ValidationError, match="response storage must remain disabled"):
        Settings(_env_file=None)
