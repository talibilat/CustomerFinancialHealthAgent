from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from customer_financial_health_api.settings import get_settings

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
