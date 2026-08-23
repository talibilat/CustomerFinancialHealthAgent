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
    get_effective_snapshot,
    save_confirmed_snapshot,
)


def test_saved_snapshot_can_be_read_back_with_exact_decimal_precision(db_session):
    customer = create_customer(db_session)
    db_session.commit()

    income_entries = [MoneyEntry(Decimal("1234.56"), Frequency.MONTHLY)]
    outgoing_entries = [MoneyEntry(Decimal("987.65"), Frequency.WEEKLY)]
    position = calculate_monthly_position(income_entries, outgoing_entries)

    saved = save_confirmed_snapshot(
        db_session,
        customer_id=customer.id,
        statement_period=date(2026, 8, 1),
        confirmed_at=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        position=position,
        income_entries=income_entries,
        outgoing_entries=outgoing_entries,
        resilience=calculate_resilience(),
    )
    db_session.commit()

    fetched = get_effective_snapshot(db_session, customer_id=customer.id)

    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.normalized_monthly_income == Decimal("1234.56")
    assert fetched.normalized_monthly_outgoings == position.normalized_monthly_outgoings
    assert fetched.monthly_headroom == position.monthly_headroom
    assert fetched.calculation_policy_version == position.calculation_policy_version
    assert len(fetched.income_entries) == 1
    assert fetched.income_entries[0].original_amount == Decimal("1234.56")
    assert fetched.income_entries[0].original_frequency == Frequency.MONTHLY
    assert len(fetched.outgoing_entries) == 1
    assert fetched.outgoing_entries[0].original_amount == Decimal("987.65")
    assert fetched.outgoing_entries[0].original_frequency == Frequency.WEEKLY


def test_confirmed_snapshot_records_what_the_customer_reported_and_settled(db_session):
    """A snapshot must reproduce the customer's own labels and meanings."""
    from customer_financial_health_api.domain.classification import (
        TAXONOMY_VERSION,
        ClassificationSource,
        DisplayCategory,
        OutgoingTreatment,
        classify_outgoing,
    )
    from customer_financial_health_api.domain.statement import StatementEntry

    customer = create_customer(db_session)
    db_session.commit()

    income = [StatementEntry("i1", "Wages", Decimal("2450.00"), Frequency.MONTHLY)]
    outgoings = [
        StatementEntry("o1", "Rent", Decimal("950.00"), Frequency.MONTHLY),
        StatementEntry("o2", "Apple", Decimal("9.99"), Frequency.MONTHLY),
    ]
    classifications = {
        "o1": classify_outgoing("Rent", preferences=()),
        "o2": classify_outgoing("Apple", preferences=()).confirmed_as(
            display_category=DisplayCategory.LEISURE_AND_HOBBIES,
            outgoing_treatment=OutgoingTreatment.FLEXIBLE_LIVING_COST,
        ),
    }

    save_confirmed_snapshot(
        db_session,
        customer_id=customer.id,
        statement_period=date(2026, 8, 1),
        confirmed_at=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        position=calculate_monthly_position(
            [e.as_money_entry() for e in income], [e.as_money_entry() for e in outgoings]
        ),
        income_entries=income,
        outgoing_entries=outgoings,
        resilience=calculate_resilience(),
        classifications=classifications,
    )
    db_session.commit()

    fetched = get_effective_snapshot(db_session, customer_id=customer.id)

    assert fetched.income_entries[0].description == "Wages"
    rent, apple = fetched.outgoing_entries
    assert rent.description == "Rent"
    assert rent.display_category == DisplayCategory.HOUSING
    assert rent.outgoing_treatment == OutgoingTreatment.PROTECTED_OUTGOING
    assert rent.classification_source == ClassificationSource.DETERMINISTIC_RULE
    assert apple.description == "Apple"
    assert apple.display_category == DisplayCategory.LEISURE_AND_HOBBIES
    assert apple.classification_source == ClassificationSource.CUSTOMER_CONFIRMATION
    assert apple.taxonomy_version == TAXONOMY_VERSION
