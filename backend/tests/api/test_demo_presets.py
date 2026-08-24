from datetime import date, datetime, timezone
from decimal import Decimal

from customer_financial_health_api.api.dependencies import get_classification_provider
from customer_financial_health_api.persistence.repository import (
    create_customer,
    get_effective_snapshot,
    save_confirmed_snapshot,
)
from customer_financial_health_api.domain.financial_health import (
    Frequency,
    MoneyEntry,
    calculate_monthly_position,
    calculate_resilience,
)
from customer_financial_health_api.settings import get_settings
from customer_financial_health_api.persistence.seed import seed_demo_data
import pytest


EXPECTED_PRESETS = {
    "zero_income",
    "reported_shortfall",
    "protected_outgoings_not_covered",
    "mixed_resilience",
    "repayment_near_buffer",
    "ambiguous_apple",
    "improving_history",
    "correction",
    "azure_unavailable",
}


def test_lists_the_nine_fictional_demo_presets(client):
    response = client.get("/demo/presets")

    assert response.status_code == 200
    presets = response.json()["presets"]
    assert {preset["code"] for preset in presets} == EXPECTED_PRESETS
    assert all(preset["fictional"] is True for preset in presets)


def test_reset_requires_the_customer_to_confirm_fictional_data_replacement(client, db_session):
    response = client.post(
        "/demo/reset",
        json={"preset": "zero_income", "confirmed_reset": False},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "demo_reset_confirmation_required"}


def test_reset_is_unavailable_outside_explicit_demo_mode(client):
    class ProductionSettings:
        demo_mode = False

    client.app.dependency_overrides[get_settings] = lambda: ProductionSettings()
    try:
        list_response = client.get("/demo/presets")
        response = client.post(
            "/demo/reset",
            json={"preset": "zero_income", "confirmed_reset": True},
        )
    finally:
        client.app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}
    assert list_response.status_code == 404


def test_reset_is_idempotent_and_returns_the_documented_zero_income_state(client, db_session):
    payload = {"preset": "zero_income", "confirmed_reset": True}

    first = client.post("/demo/reset", json=payload)
    first_overview = client.get("/overview").json()
    second = client.post("/demo/reset", json=payload)
    second_overview = client.get("/overview").json()

    assert first.status_code == second.status_code == 200
    assert first.json()["preset"] == second.json()["preset"] == "zero_income"
    assert first_overview == second_overview
    assert first_overview["difficulty"]["result_code"] == "zero_income"
    assert first_overview["difficulty"]["shortfall"] == "650.00"


def test_reset_does_not_change_another_customer(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    other = create_customer(db_session)
    position = calculate_monthly_position(
        [MoneyEntry(Decimal("777.00"), Frequency.MONTHLY)], []
    )
    original = save_confirmed_snapshot(
        db_session,
        customer_id=other.id,
        statement_period=date(2026, 1, 1),
        confirmed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        position=position,
        income_entries=[MoneyEntry(Decimal("777.00"), Frequency.MONTHLY)],
        outgoing_entries=[],
        resilience=calculate_resilience(),
    )
    db_session.commit()

    response = client.post(
        "/demo/reset",
        json={"preset": "reported_shortfall", "confirmed_reset": True},
    )

    assert response.status_code == 200
    unchanged = get_effective_snapshot(db_session, customer_id=other.id)
    assert unchanged is not None
    assert unchanged.id == original.id
    assert unchanged.monthly_headroom == Decimal("777.00")


def test_unknown_preset_returns_a_safe_closed_error(client):
    response = client.post(
        "/demo/reset",
        json={"preset": "customer-supplied", "confirmed_reset": True},
    )

    assert response.status_code == 422
    assert "customer-supplied" not in response.text


def test_azure_unavailable_preset_never_uses_provider_authority(client):
    class ProviderThatMustNotRun:
        def suggest(self, request):
            raise AssertionError("Azure provider was called")

    client.post(
        "/demo/reset",
        json={"preset": "azure_unavailable", "confirmed_reset": True},
    )
    client.app.dependency_overrides[get_classification_provider] = lambda: ProviderThatMustNotRun()
    try:
        response = client.get("/financial-statement?statement_period=2026-08-01")
    finally:
        client.app.dependency_overrides[get_classification_provider] = lambda: None

    assert response.status_code == 200
    pottery = response.json()["statement"]["outgoing_entries"][-1]
    assert pottery["description"] == "Weekend pottery"
    assert pottery["classification"]["requires_confirmation"] is True
    assert pottery["classification"]["suggestion"] is None


@pytest.mark.parametrize(
    ("preset", "difficulty_code"),
    [
        ("zero_income", "zero_income"),
        ("reported_shortfall", "reported_shortfall"),
        ("protected_outgoings_not_covered", "protected_outgoings_not_covered"),
        ("mixed_resilience", "no_difficulty_identified"),
        ("repayment_near_buffer", "no_difficulty_identified"),
        ("ambiguous_apple", "no_difficulty_identified"),
        ("improving_history", "no_difficulty_identified"),
        ("correction", "no_difficulty_identified"),
        ("azure_unavailable", "no_difficulty_identified"),
    ],
)
def test_each_preset_produces_its_documented_deterministic_state(
    client, db_session, preset, difficulty_code
):
    response = client.post(
        "/demo/reset",
        json={"preset": preset, "confirmed_reset": True},
    )

    assert response.status_code == 200
    overview = client.get("/overview").json()
    assert overview["difficulty"]["result_code"] == difficulty_code

    if preset == "mixed_resilience":
        assert overview["monthly_headroom"] == "500.00"
        assert overview["resilience"]["result_code"] == "below_reserve"
    if preset == "improving_history":
        assert client.get("/history").json()["total"] == 3
    if preset == "correction":
        history = client.get("/history").json()
        assert history["total"] == 2
        assert any(snapshot["supersedes_snapshot_id"] for snapshot in history["snapshots"])
    if preset in {"ambiguous_apple", "azure_unavailable"}:
        editor = client.get("/financial-statement?statement_period=2026-08-01").json()
        assert editor["statement"]["outgoing_entries"][-1]["classification"]["requires_confirmation"] is True
