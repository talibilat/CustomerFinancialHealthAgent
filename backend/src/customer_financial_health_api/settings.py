from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Non-secret local-dev default matching .env.example; override via DATABASE_URL
    # in every real environment. Kept lazy: nothing here opens a connection.
    database_url: str = (
        "postgresql+psycopg://financial_health:financial_health_local_only@db:5432/financial_health"
    )
    demo_mode: bool = True
    frontend_origin: str = "http://localhost:5173"


def get_settings() -> Settings:
    return Settings()
