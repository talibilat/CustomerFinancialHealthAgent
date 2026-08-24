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


def test_invalid_environment_values_are_not_echoed_in_validation_errors(monkeypatch):
    misplaced_secret = "super-secret-value"
    monkeypatch.setenv("AZURE_OPENAI_AUTH_MODE", misplaced_secret)

    with pytest.raises(ValidationError) as raised:
        Settings(_env_file=None)

    assert misplaced_secret not in str(raised.value)
