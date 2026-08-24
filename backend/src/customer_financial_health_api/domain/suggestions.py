"""Validating an unconfirmed classification suggestion from a provider.

Structured output guarantees a shape, not trustworthiness. Everything a
provider returns is treated as untrusted text and must survive these checks
before a customer is even shown it. Anything that fails becomes no suggestion
at all, which leaves the customer classifying manually - a complete path.

A suggestion is never a classification. It carries no source and no resolved
flag, precisely so it cannot be mistaken for something the customer settled.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from customer_financial_health_api.domain.classification import (
    _AMBIGUOUS,
    DisplayCategory,
    OutgoingTreatment,
)

MAX_SUGGESTION_REASON_LENGTH = 200

_ALLOWED_KEYS = frozenset(
    {"display_category", "outgoing_treatment", "confidence", "reason", "requires_clarification"}
)

_MARKUP = re.compile(r"[<>]")
_LINK = re.compile(r"https?://|www\.", re.IGNORECASE)
# The provider is given no amounts, so any figure it states is ungrounded.
_DIGIT = re.compile(r"\d")

# Wording that would exceed the provider's authority: confirming, saving,
# advising on payment, or trying to redirect the application.
_AUTHORITY_CLAIMS = (
    "confirmed",
    "i have saved",
    "saved this",
    "you should pay",
    "you must pay",
    "ignore previous",
    "ignore all previous",
    "disregard",
    "system prompt",
    "you can afford",
    "affordable",
    "recommend",
    "deployment",
    "api key",
    "endpoint",
    "environment variable",
    "authorization",
    "credential",
)


@dataclass(frozen=True)
class ProviderSuggestion:
    """An unconfirmed proposal. The customer decides; this never does."""

    display_category: DisplayCategory
    outgoing_treatment: OutgoingTreatment
    confidence: Decimal
    reason: str
    requires_clarification: bool


def _parse_confidence(raw: Any) -> Decimal | None:
    if isinstance(raw, bool) or not isinstance(raw, (str, int, Decimal)):
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    if not value.is_finite() or not (Decimal("0") <= value <= Decimal("1")):
        return None
    return value


def _reason_is_safe(reason: Any) -> bool:
    if not isinstance(reason, str):
        return False
    text = reason.strip()
    if not text or len(text) > MAX_SUGGESTION_REASON_LENGTH:
        return False
    if _MARKUP.search(text) or _LINK.search(text) or _DIGIT.search(text):
        return False
    lowered = text.casefold()
    return not any(claim in lowered for claim in _AUTHORITY_CLAIMS)


def validate_provider_suggestion(
    payload: Any, *, normalized_description: str
) -> ProviderSuggestion | None:
    """Return a usable suggestion, or ``None`` to fall back to manual classification.

    Returning ``None`` is always safe: the customer classifies the entry
    themselves, which is the same path taken when no provider is configured.
    """
    if not isinstance(payload, Mapping):
        return None
    # Closed: an unexpected key means the output is not what was asked for.
    if set(payload) - _ALLOWED_KEYS:
        return None

    try:
        category = DisplayCategory(payload.get("display_category"))
        treatment = OutgoingTreatment(payload.get("outgoing_treatment"))
    except (ValueError, TypeError):
        return None

    confidence = _parse_confidence(payload.get("confidence"))
    if confidence is None:
        return None

    reason = payload.get("reason")
    if not _reason_is_safe(reason):
        return None

    requires_clarification = payload.get("requires_clarification")
    if not isinstance(requires_clarification, bool):
        return None

    # Business policy outranks model certainty: a merchant name or a movement of
    # money always goes back to the customer, however confident the provider is.
    if normalized_description in _AMBIGUOUS:
        requires_clarification = True

    return ProviderSuggestion(
        display_category=category,
        outgoing_treatment=treatment,
        confidence=confidence,
        reason=reason.strip(),
        requires_clarification=requires_clarification,
    )
