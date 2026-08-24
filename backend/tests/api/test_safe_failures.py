"""Operational safety: what leaks when things go wrong."""

import logging

import pytest

from customer_financial_health_api.persistence.seed import seed_demo_data

SECRETS = ("Traceback", "psycopg", "SELECT ", "postgresql://", "postgresql+psycopg", "sqlalchemy")


@pytest.fixture()
def seeded(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    return client


class TestInternalFailures:
    def test_an_unexpected_error_returns_a_correlation_id_and_no_internals(
        self, seeded, monkeypatch
    ):
        import customer_financial_health_api.api.routers.overview as overview_router

        def explode(*args, **kwargs):
            raise RuntimeError(
                "connect to postgresql+psycopg://cfha:secret@db/financial_health failed"
            )

        monkeypatch.setattr(overview_router, "get_effective_snapshot", explode)

        response = seeded.get("/overview")

        assert response.status_code == 500
        body = response.json()
        assert body["detail"]["code"] == "internal_error"
        assert body["detail"]["correlation_id"]
        for secret in SECRETS:
            assert secret not in response.text, secret
        assert "secret" not in response.text

    def test_the_correlation_id_differs_between_failures(self, seeded, monkeypatch):
        import customer_financial_health_api.api.routers.overview as overview_router

        monkeypatch.setattr(
            overview_router,
            "get_effective_snapshot",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        first = seeded.get("/overview").json()["detail"]["correlation_id"]
        second = seeded.get("/overview").json()["detail"]["correlation_id"]

        assert first != second


class TestMalformedRequests:
    def test_malformed_json_is_a_stable_client_error(self, seeded):
        response = seeded.post(
            "/financial-statement/preview",
            content="{not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422
        for secret in SECRETS:
            assert secret not in response.text

    def test_a_wrong_content_type_is_refused_without_internals(self, seeded):
        response = seeded.post(
            "/financial-statement/preview",
            content="statement_period=2026-08-01",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code in {415, 422}
        assert "Traceback" not in response.text


class TestLogsOmitSensitiveValues:
    def test_a_failure_logs_a_correlation_id_but_no_financial_detail(
        self, seeded, monkeypatch, caplog
    ):
        import customer_financial_health_api.api.routers.overview as overview_router

        monkeypatch.setattr(
            overview_router,
            "get_effective_snapshot",
            lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError("rent 950.00 for postgresql://cfha:secret@db/x")
            ),
        )

        with caplog.at_level(logging.ERROR):
            response = seeded.get("/overview")

        # The middleware must have handled it; otherwise there is nothing to log.
        assert response.status_code == 500, response.text[:200]

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "correlation_id" in logged or any(
            getattr(r, "correlation_id", None) for r in caplog.records
        )
        assert "secret" not in logged
        assert "950.00" not in logged


class TestHealthBoundaries:
    def test_liveness_does_not_depend_on_the_database(self, client, monkeypatch):
        import customer_financial_health_api.api.routers.health as health_router

        if hasattr(health_router, "_check_database"):
            monkeypatch.setattr(
                health_router,
                "_check_database",
                lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")),
            )

        response = client.get("/health/live")

        assert response.status_code == 200

    def test_readiness_reports_the_optional_provider_separately(self, client):
        body = client.get("/health/ready").json()

        assert body["status"] == "ready"
        assert body["database"] == "ok"
        # AI is optional: its absence must not make the application unready, and
        # its status is reported separately rather than folded into readiness.
        assert "optional_capabilities" in body


class TestCors:
    def test_cors_uses_an_explicit_origin_rather_than_a_wildcard(self, client):
        response = client.get("/health/live", headers={"Origin": "http://localhost:5173"})

        allowed = response.headers.get("access-control-allow-origin")
        assert allowed == "http://localhost:5173"
        assert allowed != "*"

    def test_an_unapproved_origin_is_not_granted_access(self, client):
        response = client.get("/health/live", headers={"Origin": "http://evil.example"})

        assert response.headers.get("access-control-allow-origin") != "http://evil.example"
