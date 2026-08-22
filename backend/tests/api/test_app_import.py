import importlib
import os

import pytest


def test_app_module_imports_without_database_url_set(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    import customer_financial_health_api.api.app as app_module

    try:
        importlib.reload(app_module)
    except Exception as exc:
        pytest.fail(f"importing the app should not require DATABASE_URL to be set: {exc}")
