from typing import Literal

from pydantic import NonNegativeInt, PositiveFloat, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    # Non-secret local-dev default matching .env.example; override via DATABASE_URL
    # in every real environment. Kept lazy: nothing here opens a connection.
    database_url: str = (
        "postgresql+psycopg://financial_health:financial_health_local_only@db:5432/financial_health"
    )
    demo_mode: bool = True
    frontend_origin: str = "http://localhost:5173"

    azure_openai_endpoint: str | None = None
    azure_openai_classification_deployment: str | None = None
    azure_openai_guidance_deployment: str | None = None
    azure_openai_auth_mode: Literal["api_key", "entra_id"] = "api_key"
    azure_openai_api_key: SecretStr | None = None
    azure_openai_timeout_seconds: PositiveFloat = 10
    azure_openai_max_retries: NonNegativeInt = 1
    azure_openai_store: bool = False
    azure_client_id: str | None = None

    @field_validator("azure_openai_store")
    @classmethod
    def ai_storage_must_stay_disabled(cls, value: bool) -> bool:
        if value:
            raise ValueError("Azure OpenAI response storage must remain disabled")
        return value


def get_settings() -> Settings:
    return Settings()
