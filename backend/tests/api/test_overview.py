import pytest

from customer_financial_health_api.persistence.seed import seed_demo_data


def test_overview_returns_404_when_no_customer_data_exists(client, db_session):
    response = client.get("/overview")

    assert response.status_code == 404


def test_overview_returns_closed_schema_for_seeded_customer(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()

    response = client.get("/overview")

    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == {
        "customer_id",
        "statement_period",
        "confirmed_at",
        "calculation_policy_version",
        "normalized_monthly_income",
        "normalized_monthly_outgoings",
        "monthly_headroom",
        "result_code",
        "warnings",
        "income_entries",
        "outgoing_entries",
    }
    assert body["normalized_monthly_income"] == "2450.00"
    assert body["result_code"] in {"surplus", "balanced", "shortfall"}
    assert len(body["income_entries"]) == 1
    assert set(body["income_entries"][0].keys()) == {
        "original_amount",
        "original_frequency",
        "normalized_monthly_amount",
    }


def test_overview_rejects_client_supplied_calculated_fields():
    from customer_financial_health_api.api.schemas import OverviewResponse

    with pytest.raises(Exception):
        OverviewResponse(
            customer_id="abc",
            statement_period="2026-08-01",
            confirmed_at="2026-08-01T00:00:00Z",
            calculation_policy_version="v1",
            normalized_monthly_income="100.00",
            normalized_monthly_outgoings="50.00",
            monthly_headroom="50.00",
            result_code="surplus",
            warnings=[],
            income_entries=[],
            outgoing_entries=[],
            monthly_headroom_override="9999.00",
        )
