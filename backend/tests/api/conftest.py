import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://cfha:cfha_test_password@localhost:55432/customer_financial_health_test",
)


@pytest.fixture(scope="session", autouse=True)
def _configure_database_url():
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest.fixture(scope="session")
def engine(_configure_database_url):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    backend_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(engine):
    from customer_financial_health_api.persistence.models import Base

    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(engine):
    from customer_financial_health_api.api.app import app
    from customer_financial_health_api.api.dependencies import get_classification_provider

    app.dependency_overrides[get_classification_provider] = lambda: None
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_classification_provider, None)
