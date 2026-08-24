"""Deterministic classification, optionally assisted by a provider.

The order is unchanged: a customer's own preference, then deterministic rules,
then - only if the entry is still unsettled - an optional provider that may
propose something. A proposal never resolves anything; the customer does.

Every provider failure resolves to no suggestion, which is exactly the state
the product is in when no provider is configured at all. That is why the
journey stays complete without Azure.
"""

import logging
from dataclasses import replace
from typing import Protocol, Sequence

from customer_financial_health_api.domain.classification import (
    ClassificationOutcome,
    CustomerPreference,
    DisplayCategory,
    OutgoingTreatment,
    classify_outgoing,
)
from customer_financial_health_api.domain.suggestions import validate_provider_suggestion

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = tuple(category.value for category in DisplayCategory)
ALLOWED_TREATMENTS = tuple(treatment.value for treatment in OutgoingTreatment)


class ClassificationSuggestionProvider(Protocol):
    """A source of unconfirmed proposals. Given a description and nothing else."""

    def suggest(
        self,
        *,
        description: str,
        allowed_categories: Sequence[str],
        allowed_treatments: Sequence[str],
    ) -> object | None:
        ...


def classify_with_suggestions(
    description: str,
    *,
    preferences: tuple[CustomerPreference, ...] = (),
    provider: ClassificationSuggestionProvider | None = None,
) -> ClassificationOutcome:
    """Classify an outgoing, asking a provider only when nothing else settled it."""
    outcome = classify_outgoing(description, preferences=preferences)

    # A preference or a rule already decided. A provider has nothing to add and
    # must not be given the chance to contradict it.
    if outcome.is_resolved or provider is None:
        return outcome

    try:
        raw = provider.suggest(
            description=description,
            allowed_categories=ALLOWED_CATEGORIES,
            allowed_treatments=ALLOWED_TREATMENTS,
        )
    except Exception:
        # Timeout, connection failure, 401, 403, 429, 5xx, refusal, filtering:
        # all the same from here. The customer classifies manually.
        logger.info(
            "classification_suggestion_unavailable",
            extra={"outcome": "fallback", "reason": "provider_error"},
        )
        return outcome

    suggestion = validate_provider_suggestion(
        raw, normalized_description=outcome.normalized_description
    )
    if suggestion is None:
        logger.info(
            "classification_suggestion_rejected",
            extra={"outcome": "fallback", "reason": "output_failed_validation"},
        )
        return outcome

    return replace(outcome, suggestion=suggestion)
