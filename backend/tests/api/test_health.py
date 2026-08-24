def test_liveness_reports_ok(client):
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_ready_when_database_and_migrations_are_healthy(client, db_session):
    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["optional_capabilities"] == {
        "classification_suggestions": "not_configured",
        "personalized_guidance": "not_configured",
    }


def test_readiness_stays_ready_and_reports_configured_optional_ai(client, db_session):
    from customer_financial_health_api.api.app import app
    from customer_financial_health_api.settings import Settings, get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused-by-overridden-db",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_classification_deployment="classify-v1",
        azure_openai_guidance_deployment="guidance-v1",
        azure_openai_api_key="not-a-real-key",
    )
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["optional_capabilities"] == {
        "classification_suggestions": "configured",
        "personalized_guidance": "configured",
    }
