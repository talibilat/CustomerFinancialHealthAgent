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
        "snapshot_id",
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
        "resilience",
        "difficulty",
        "deterministic_explanation",
        "personalized_explanation",
    }
    assert body["normalized_monthly_income"] == "2450.00"
    assert body["result_code"] in {"surplus", "balanced", "shortfall"}
    assert len(body["income_entries"]) == 1
    assert set(body["income_entries"][0].keys()) == {
        "original_amount",
        "original_frequency",
        "normalized_monthly_amount",
    }


def test_overview_resilience_is_below_reserve_for_seeded_customer(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()

    response = client.get("/overview")

    resilience = response.json()["resilience"]
    assert set(resilience.keys()) == {
        "accessible_savings",
        "protected_reserve",
        "current_account_balance",
        "known_arrears",
        "savings_above_reserve",
        "reserve_gap",
        "result_code",
        "warnings",
    }
    assert resilience["accessible_savings"] == "300.00"
    assert resilience["protected_reserve"] == "1000.00"
    assert resilience["current_account_balance"] == "-45.30"
    assert resilience["reserve_gap"] == "700.00"
    assert resilience["result_code"] == "below_reserve"
    assert resilience["warnings"] == []


def test_overview_missing_resilience_data_does_not_change_monthly_headroom(client, db_session):
    from datetime import date, datetime, timezone
    from decimal import Decimal

    from customer_financial_health_api.domain.financial_health import (
        Frequency,
        MoneyEntry,
        calculate_monthly_position,
        calculate_resilience,
    )
    from customer_financial_health_api.persistence.repository import (
        create_customer,
        save_confirmed_snapshot,
    )

    customer = create_customer(db_session)
    db_session.commit()
    income_entries = [MoneyEntry(Decimal("1000.00"), Frequency.MONTHLY)]
    position = calculate_monthly_position(income_entries, [])
    save_confirmed_snapshot(
        db_session,
        customer_id=customer.id,
        statement_period=date(2026, 8, 1),
        confirmed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        position=position,
        income_entries=income_entries,
        outgoing_entries=[],
        resilience=calculate_resilience(),
    )
    db_session.commit()

    response = client.get("/overview")

    body = response.json()
    assert body["monthly_headroom"] == "1000.00"
    assert body["resilience"]["result_code"] is None
    assert "resilience_info_missing" in body["resilience"]["warnings"]


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
