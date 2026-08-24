from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from customer_financial_health_api.api.dependencies import get_guidance_generator
from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.statement import FinancialStatement, StatementEntry
from customer_financial_health_api.persistence.repository import (
    correct_snapshot,
    get_demo_customer,
    get_latest_personalized_explanation,
)
from customer_financial_health_api.persistence.seed import (
    INCOME_ENTRIES,
    OUTGOING_ENTRIES,
    seed_demo_data,
)


class SafeGenerator:
    deployment = "guidance-v1"

    def generate(self, facts):
        return {
            "text": (
                "Your reported monthly income is £2,450.00 and your reported monthly "
                "outgoings are £1,518.75. This leaves £931.25 of monthly headroom."
            ),
            "result_code": facts.result_code,
            "warning_codes": list(facts.warning_codes),
            "support_codes": list(facts.support_codes),
            "referenced_fact_keys": [
                "normalized_monthly_income",
                "normalized_monthly_outgoings",
                "monthly_headroom",
            ],
        }


def correct_seeded_snapshot(db_session, original):
    customer = get_demo_customer(db_session)
    assert customer is not None
    corrected_outgoings = (
        StatementEntry(
            OUTGOING_ENTRIES[0].entry_id,
            OUTGOING_ENTRIES[0].description,
            Decimal("951.00"),
            OUTGOING_ENTRIES[0].frequency,
        ),
        *OUTGOING_ENTRIES[1:],
    )
    statement = FinancialStatement(
        statement_period=date.fromisoformat(original["statement_period"]),
        income_entries=INCOME_ENTRIES,
        outgoing_entries=corrected_outgoings,
        repayment_commitments=(),
    )
    classifications = {
        entry.entry_id: classify_outgoing(entry.description, preferences=())
        for entry in corrected_outgoings
    }
    corrected = correct_snapshot(
        db_session,
        customer_id=customer.id,
        supersedes_snapshot_id=UUID(original["snapshot_id"]),
        statement=statement,
        classifications=classifications,
        correction_reason="The reported rent was one pound too low.",
        idempotency_key="correct-after-guidance",
        confirmed_at=datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
    )
    db_session.commit()
    return customer, corrected


def test_customer_requests_snapshot_bound_wording_without_losing_deterministic_copy(
    client, db_session
):
    seed_demo_data(db_session)
    db_session.commit()
    client.app.dependency_overrides[get_guidance_generator] = lambda: SafeGenerator()
    try:
        before = client.get("/overview")
        snapshot_id = before.json()["snapshot_id"]

        response = client.post(
            "/overview/personalized-explanation",
            json={"snapshot_id": snapshot_id},
            headers={"Idempotency-Key": "guidance-request-1"},
        )
        after = client.get("/overview")
    finally:
        client.app.dependency_overrides.pop(get_guidance_generator, None)

    assert before.status_code == response.status_code == after.status_code == 200
    assert before.json()["deterministic_explanation"]
    assert before.json()["personalized_explanation"] is None
    assert response.json()["snapshot_id"] == snapshot_id
    assert response.json()["outcome"] == "generated"
    assert response.json()["text"].endswith("£931.25 of monthly headroom.")
    assert after.json()["deterministic_explanation"] == before.json()[
        "deterministic_explanation"
    ]
    assert after.json()["personalized_explanation"] == response.json()


def test_unconfigured_provider_returns_and_persists_calm_deterministic_fallback(
    client, db_session
):
    seed_demo_data(db_session)
    db_session.commit()
    overview = client.get("/overview").json()

    response = client.post(
        "/overview/personalized-explanation",
        json={"snapshot_id": overview["snapshot_id"]},
        headers={"Idempotency-Key": "fallback-1"},
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "fallback_not_configured"
    assert response.json()["text"] == overview["deterministic_explanation"]
    refreshed = client.get("/overview").json()
    assert refreshed["difficulty"] == overview["difficulty"]
    assert refreshed["personalized_explanation"]["snapshot_id"] == overview["snapshot_id"]


def test_saved_wording_never_becomes_current_for_a_corrected_snapshot(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    original = client.get("/overview").json()
    generated = client.post(
        "/overview/personalized-explanation",
        json={"snapshot_id": original["snapshot_id"]},
        headers={"Idempotency-Key": "before-correction"},
    )
    assert generated.status_code == 200

    _, corrected = correct_seeded_snapshot(db_session, original)

    refreshed = client.get("/overview").json()
    assert refreshed["snapshot_id"] == str(corrected.id)
    assert refreshed["snapshot_id"] != original["snapshot_id"]
    assert refreshed["personalized_explanation"] is None


def test_wording_is_not_saved_if_the_snapshot_changes_during_generation(
    client, db_session
):
    seed_demo_data(db_session)
    db_session.commit()
    original = client.get("/overview").json()

    class CorrectingGenerator(SafeGenerator):
        def generate(self, facts):
            correct_seeded_snapshot(db_session, original)
            return super().generate(facts)

    client.app.dependency_overrides[get_guidance_generator] = CorrectingGenerator
    try:
        response = client.post(
            "/overview/personalized-explanation",
            json={"snapshot_id": original["snapshot_id"]},
            headers={"Idempotency-Key": "raced-correction"},
        )
    finally:
        client.app.dependency_overrides.pop(get_guidance_generator, None)

    customer = get_demo_customer(db_session)
    assert customer is not None
    assert response.status_code == 409
    assert response.json()["detail"] == "snapshot_no_longer_effective"
    assert get_latest_personalized_explanation(
        db_session,
        customer_id=customer.id,
        snapshot_id=UUID(original["snapshot_id"]),
    ) is None


def test_guidance_request_is_closed_and_rejects_a_non_current_snapshot(client, db_session):
    seed_demo_data(db_session)
    db_session.commit()
    current = client.get("/overview").json()["snapshot_id"]

    extra = client.post(
        "/overview/personalized-explanation",
        json={"snapshot_id": current, "result_code": "surplus"},
        headers={"Idempotency-Key": "closed-1"},
    )
    stale = client.post(
        "/overview/personalized-explanation",
        json={"snapshot_id": str(uuid4())},
        headers={"Idempotency-Key": "stale-1"},
    )

    assert extra.status_code == 422
    assert stale.status_code == 409
    assert stale.json()["detail"] == "snapshot_no_longer_effective"
