from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from customer_financial_health_api.settings import get_settings
from customer_financial_health_api.providers.azure_openai import (
    AzureClassificationSuggestionProvider,
)
from customer_financial_health_api.providers.openai_client import (
    SharedOpenAIClient,
    build_shared_openai_client,
)

_engine = None
_session_factory = None


def _session_maker() -> sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url)
        _session_factory = sessionmaker(bind=_engine)
    return _session_factory


def get_db() -> Iterator[Session]:
    session = _session_maker()()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def get_shared_openai_client() -> SharedOpenAIClient | None:
    """One process-wide SDK client shared by the two optional AI operations."""
    return build_shared_openai_client(get_settings())


def get_classification_provider(
    configured: SharedOpenAIClient | None = Depends(get_shared_openai_client),
):
    if configured is None or configured.classification_deployment is None:
        return None
    return AzureClassificationSuggestionProvider(
        client=configured.client,
        deployment=configured.classification_deployment,
    )
