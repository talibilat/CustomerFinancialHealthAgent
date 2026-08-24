from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from customer_financial_health_api.domain.financial_health import (
    Frequency,
    MoneyEntry,
    calculate_monthly_position,
    calculate_resilience,
)
from customer_financial_health_api.domain.guidance import (
    GuidanceOutcome,
    GuidanceRequestOutcome,
)
from customer_financial_health_api.persistence.repository import (
    IdempotencyConflict,
    PersonalizedExplanationSnapshotNotFound,
    create_customer,
    get_latest_personalized_explanation,
    record_personalized_explanation,
    save_confirmed_snapshot,
)


CREATED_AT = datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc)


def basis(db_session):
    customer = create_customer(db_session)
    income = (MoneyEntry(Decimal("2450.00"), Frequency.MONTHLY),)
    outgoings = (MoneyEntry(Decimal("1950.00"), Frequency.MONTHLY),)
    snapshot = save_confirmed_snapshot(
        db_session,
        customer_id=customer.id,
        statement_period=date(2026, 8, 1),
        confirmed_at=datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc),
        position=calculate_monthly_position(income, outgoings),
        income_entries=income,
        outgoing_entries=outgoings,
        resilience=calculate_resilience(),
    )
    db_session.commit()
    return customer, snapshot


def explanation():
    return GuidanceOutcome(
        text="Your reported figures leave £500.00 of monthly headroom.",
        outcome=GuidanceRequestOutcome.GENERATED,
        deployment="guidance-v1",
    )


def test_personalized_wording_is_owned_and_bound_to_one_snapshot(db_session):
    customer, snapshot = basis(db_session)

    recorded = record_personalized_explanation(
        db_session,
        customer_id=customer.id,
        snapshot_id=snapshot.id,
        explanation=explanation(),
        idempotency_key="guidance-1",
        request_fingerprint="fingerprint-1",
        created_at=CREATED_AT,
    )
    db_session.commit()

    fetched = get_latest_personalized_explanation(
        db_session, customer_id=customer.id, snapshot_id=snapshot.id
    )
    assert fetched == recorded
    assert fetched.text == "Your reported figures leave £500.00 of monthly headroom."
    assert fetched.snapshot_id == snapshot.id
    assert fetched.customer_id == customer.id
    assert fetched.outcome is GuidanceRequestOutcome.GENERATED
    assert fetched.deployment == "guidance-v1"
    assert fetched.prompt_version == "guidance-prompt-v1"
    assert fetched.schema_version == "guidance-schema-v1"
    assert fetched.created_at == CREATED_AT


def test_another_customer_cannot_record_or_read_wording_for_the_snapshot(db_session):
    owner, snapshot = basis(db_session)
    stranger = create_customer(db_session)
    db_session.commit()

    with pytest.raises(PersonalizedExplanationSnapshotNotFound):
        record_personalized_explanation(
            db_session,
            customer_id=stranger.id,
            snapshot_id=snapshot.id,
            explanation=explanation(),
            idempotency_key="stranger-guidance",
            request_fingerprint="stranger-fingerprint",
            created_at=CREATED_AT,
        )

    assert get_latest_personalized_explanation(
        db_session, customer_id=stranger.id, snapshot_id=snapshot.id
    ) is None
    assert get_latest_personalized_explanation(
        db_session, customer_id=owner.id, snapshot_id=snapshot.id
    ) is None


def test_guidance_request_retry_is_idempotent_and_changed_body_conflicts(db_session):
    customer, snapshot = basis(db_session)
    first = record_personalized_explanation(
        db_session,
        customer_id=customer.id,
        snapshot_id=snapshot.id,
        explanation=explanation(),
        idempotency_key="guidance-1",
        request_fingerprint="same",
        created_at=CREATED_AT,
    )
    db_session.commit()

    retried = record_personalized_explanation(
        db_session,
        customer_id=customer.id,
        snapshot_id=snapshot.id,
        explanation=explanation(),
        idempotency_key="guidance-1",
        request_fingerprint="same",
        created_at=CREATED_AT,
    )
    assert retried.id == first.id

    with pytest.raises(IdempotencyConflict):
        record_personalized_explanation(
            db_session,
            customer_id=customer.id,
            snapshot_id=snapshot.id,
            explanation=explanation(),
            idempotency_key="guidance-1",
            request_fingerprint="changed",
            created_at=CREATED_AT,
        )
