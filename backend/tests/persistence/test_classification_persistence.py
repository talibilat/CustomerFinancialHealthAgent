from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from customer_financial_health_api.domain.classification import (
    TAXONOMY_VERSION,
    ClassificationSource,
    CustomerPreference,
    DisplayCategory,
    OutgoingTreatment,
    classify_outgoing,
    normalize_description,
)
from customer_financial_health_api.domain.statement import validate_statement
from customer_financial_health_api.persistence.repository import (
    create_customer,
    get_customer_preferences,
    get_editable_statement,
    save_customer_preference,
    save_editable_statement,
)

PERIOD = date(2026, 8, 1)


def payload(**overrides):
    base = {
        "statement_period": PERIOD.isoformat(),
        "income_entries": [
            {"entry_id": "i1", "description": "Wages", "amount": "2450.00", "frequency": "monthly"}
        ],
        "outgoing_entries": [
            {"entry_id": "o1", "description": "Rent", "amount": "950.00", "frequency": "monthly"},
            {"entry_id": "o2", "description": "Apple", "amount": "9.99", "frequency": "monthly"},
        ],
        "repayment_commitments": [],
    }
    base.update(overrides)
    return base


def preference(description: str, category: DisplayCategory, treatment: OutgoingTreatment):
    return CustomerPreference(
        normalized_description=normalize_description(description),
        display_category=category,
        outgoing_treatment=treatment,
    )


class TestPreferences:
    def test_a_saved_preference_round_trips_for_its_owner(self, db_session):
        customer = create_customer(db_session)
        save_customer_preference(
            db_session,
            customer_id=customer.id,
            preference=preference(
                "Dance Class", DisplayCategory.LEISURE_AND_HOBBIES, OutgoingTreatment.FLEXIBLE_LIVING_COST
            ),
        )
        db_session.commit()

        stored = get_customer_preferences(db_session, customer_id=customer.id)

        assert len(stored) == 1
        assert stored[0].normalized_description == "dance class"
        assert stored[0].display_category == DisplayCategory.LEISURE_AND_HOBBIES
        assert stored[0].outgoing_treatment == OutgoingTreatment.FLEXIBLE_LIVING_COST

    def test_preferences_never_leak_between_customers(self, db_session):
        owner = create_customer(db_session)
        other = create_customer(db_session)
        save_customer_preference(
            db_session,
            customer_id=owner.id,
            preference=preference(
                "Dance Class", DisplayCategory.LEISURE_AND_HOBBIES, OutgoingTreatment.FLEXIBLE_LIVING_COST
            ),
        )
        db_session.commit()

        assert get_customer_preferences(db_session, customer_id=other.id) == ()
        assert len(get_customer_preferences(db_session, customer_id=owner.id)) == 1

    def test_correcting_the_same_phrase_updates_rather_than_duplicates(self, db_session):
        customer = create_customer(db_session)
        save_customer_preference(
            db_session,
            customer_id=customer.id,
            preference=preference("Apple", DisplayCategory.FOOD_AND_HOUSEKEEPING, OutgoingTreatment.PROTECTED_OUTGOING),
        )
        db_session.commit()

        save_customer_preference(
            db_session,
            customer_id=customer.id,
            preference=preference(
                "apple", DisplayCategory.LEISURE_AND_HOBBIES, OutgoingTreatment.FLEXIBLE_LIVING_COST
            ),
        )
        db_session.commit()

        stored = get_customer_preferences(db_session, customer_id=customer.id)
        assert len(stored) == 1
        assert stored[0].display_category == DisplayCategory.LEISURE_AND_HOBBIES

    def test_two_customers_may_hold_opposite_preferences_for_the_same_phrase(self, db_session):
        first = create_customer(db_session)
        second = create_customer(db_session)
        save_customer_preference(
            db_session,
            customer_id=first.id,
            preference=preference("Apple", DisplayCategory.LEISURE_AND_HOBBIES, OutgoingTreatment.FLEXIBLE_LIVING_COST),
        )
        save_customer_preference(
            db_session,
            customer_id=second.id,
            preference=preference("Apple", DisplayCategory.FOOD_AND_HOUSEKEEPING, OutgoingTreatment.PROTECTED_OUTGOING),
        )
        db_session.commit()

        assert get_customer_preferences(db_session, customer_id=first.id)[0].display_category == (
            DisplayCategory.LEISURE_AND_HOBBIES
        )
        assert get_customer_preferences(db_session, customer_id=second.id)[0].display_category == (
            DisplayCategory.FOOD_AND_HOUSEKEEPING
        )

    def test_a_duplicate_phrase_for_one_customer_is_refused_by_the_database(self, db_session):
        from customer_financial_health_api.persistence.models import CustomerClassificationPreference

        customer = create_customer(db_session)
        for _ in range(2):
            db_session.add(
                CustomerClassificationPreference(
                    customer_id=customer.id,
                    normalized_description="apple",
                    display_category=DisplayCategory.OTHER.value,
                    outgoing_treatment=OutgoingTreatment.FLEXIBLE_LIVING_COST.value,
                    taxonomy_version=TAXONOMY_VERSION,
                )
            )

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestConfirmedClassificationOnEntries:
    def test_a_confirmed_classification_round_trips_with_its_source_and_taxonomy_version(self, db_session):
        customer = create_customer(db_session)
        statement = validate_statement(payload())
        confirmed = classify_outgoing("Apple", preferences=()).confirmed_as(
            display_category=DisplayCategory.LEISURE_AND_HOBBIES,
            outgoing_treatment=OutgoingTreatment.FLEXIBLE_LIVING_COST,
        )

        save_editable_statement(
            db_session,
            customer_id=customer.id,
            statement=statement,
            expected_version=None,
            classifications={"o2": confirmed},
        )
        db_session.commit()

        stored = get_editable_statement(db_session, customer_id=customer.id, statement_period=PERIOD)
        apple = stored.classifications["o2"]

        assert apple.display_category == DisplayCategory.LEISURE_AND_HOBBIES
        assert apple.outgoing_treatment == OutgoingTreatment.FLEXIBLE_LIVING_COST
        assert apple.source == ClassificationSource.CUSTOMER_CONFIRMATION
        assert apple.taxonomy_version == TAXONOMY_VERSION

    def test_an_unclassified_outgoing_stores_nothing_rather_than_a_default(self, db_session):
        customer = create_customer(db_session)

        save_editable_statement(
            db_session,
            customer_id=customer.id,
            statement=validate_statement(payload()),
            expected_version=None,
            classifications={},
        )
        db_session.commit()

        stored = get_editable_statement(db_session, customer_id=customer.id, statement_period=PERIOD)

        assert "o2" not in stored.classifications

    def test_saving_a_statement_never_writes_another_customers_preference(self, db_session):
        owner = create_customer(db_session)
        other = create_customer(db_session)
        save_customer_preference(
            db_session,
            customer_id=other.id,
            preference=preference("Apple", DisplayCategory.FOOD_AND_HOUSEKEEPING, OutgoingTreatment.PROTECTED_OUTGOING),
        )
        db_session.commit()

        save_customer_preference(
            db_session,
            customer_id=owner.id,
            preference=preference("Apple", DisplayCategory.LEISURE_AND_HOBBIES, OutgoingTreatment.FLEXIBLE_LIVING_COST),
        )
        db_session.commit()

        untouched = get_customer_preferences(db_session, customer_id=other.id)
        assert untouched[0].display_category == DisplayCategory.FOOD_AND_HOUSEKEEPING
        assert untouched[0].outgoing_treatment == OutgoingTreatment.PROTECTED_OUTGOING
