"""Deterministic-first classification of a reported outgoing.

Classification resolves in a fixed order: a customer's own confirmed
preference, then deterministic global rules, then nothing. An unknown or
ambiguous description is never guessed - it stays unresolved and waits for the
customer. No provider is consulted anywhere in this module, and the whole
journey works without one.

Matching is on the *whole* normalized description, never a substring, so
"Apple Music" can never inherit the fruit-shaped reading of "apple".
"""

import re
import unicodedata
from dataclasses import dataclass, replace
from enum import Enum

TAXONOMY_VERSION = "outgoing-taxonomy-v1"

MAX_DESCRIPTION_LENGTH = 500


class OutgoingTreatment(str, Enum):
    """How an outgoing participates in explanations. Deliberately only four."""

    PROTECTED_OUTGOING = "protected_outgoing"
    EXISTING_CREDIT_COMMITMENT = "existing_credit_commitment"
    FLEXIBLE_LIVING_COST = "flexible_living_cost"
    PROTECTED_FUTURE_PROVISION = "protected_future_provision"


class DisplayCategory(str, Enum):
    HOUSING = "housing"
    COUNCIL_TAX_AND_PRIORITY_BILLS = "council_tax_and_priority_bills"
    UTILITIES = "utilities"
    FOOD_AND_HOUSEKEEPING = "food_and_housekeeping"
    TRANSPORT = "transport"
    HEALTH_AND_CARE = "health_and_care"
    CHILDREN_AND_DEPENDANTS = "children_and_dependants"
    COMMUNICATIONS = "communications"
    INSURANCE = "insurance"
    EXISTING_DEBT_REPAYMENTS = "existing_debt_repayments"
    LEISURE_AND_HOBBIES = "leisure_and_hobbies"
    SAVINGS_AND_FUTURE_PROVISIONS = "savings_and_future_provisions"
    OTHER = "other"


class ClassificationSource(str, Enum):
    CUSTOMER_PREFERENCE = "customer_preference"
    DETERMINISTIC_RULE = "deterministic_rule"
    CUSTOMER_CONFIRMATION = "customer_confirmation"


# A category's *default* treatment only. The customer may confirm a different
# one because essentiality is individual: transport or communications can be
# essential because of work, disability, or caring responsibilities.
_DEFAULT_TREATMENT: dict[DisplayCategory, OutgoingTreatment] = {
    DisplayCategory.HOUSING: OutgoingTreatment.PROTECTED_OUTGOING,
    DisplayCategory.COUNCIL_TAX_AND_PRIORITY_BILLS: OutgoingTreatment.PROTECTED_OUTGOING,
    DisplayCategory.UTILITIES: OutgoingTreatment.PROTECTED_OUTGOING,
    DisplayCategory.FOOD_AND_HOUSEKEEPING: OutgoingTreatment.PROTECTED_OUTGOING,
    DisplayCategory.TRANSPORT: OutgoingTreatment.FLEXIBLE_LIVING_COST,
    DisplayCategory.HEALTH_AND_CARE: OutgoingTreatment.PROTECTED_OUTGOING,
    DisplayCategory.CHILDREN_AND_DEPENDANTS: OutgoingTreatment.PROTECTED_OUTGOING,
    DisplayCategory.COMMUNICATIONS: OutgoingTreatment.FLEXIBLE_LIVING_COST,
    DisplayCategory.INSURANCE: OutgoingTreatment.PROTECTED_OUTGOING,
    DisplayCategory.EXISTING_DEBT_REPAYMENTS: OutgoingTreatment.EXISTING_CREDIT_COMMITMENT,
    DisplayCategory.LEISURE_AND_HOBBIES: OutgoingTreatment.FLEXIBLE_LIVING_COST,
    DisplayCategory.SAVINGS_AND_FUTURE_PROVISIONS: OutgoingTreatment.PROTECTED_FUTURE_PROVISION,
    DisplayCategory.OTHER: OutgoingTreatment.FLEXIBLE_LIVING_COST,
}


def default_treatment_for(category: DisplayCategory) -> OutgoingTreatment:
    return _DEFAULT_TREATMENT[category]


# Whole-phrase rules. Adding a phrase here is a deliberate, reviewable act.
_RULES: dict[str, DisplayCategory] = {
    "rent": DisplayCategory.HOUSING,
    "mortgage": DisplayCategory.HOUSING,
    "ground rent": DisplayCategory.HOUSING,
    "service charge": DisplayCategory.HOUSING,
    "council tax": DisplayCategory.COUNCIL_TAX_AND_PRIORITY_BILLS,
    "tv licence": DisplayCategory.COUNCIL_TAX_AND_PRIORITY_BILLS,
    "electricity": DisplayCategory.UTILITIES,
    "gas": DisplayCategory.UTILITIES,
    "water": DisplayCategory.UTILITIES,
    "energy": DisplayCategory.UTILITIES,
    "groceries": DisplayCategory.FOOD_AND_HOUSEKEEPING,
    "food shopping": DisplayCategory.FOOD_AND_HOUSEKEEPING,
    "food and housekeeping": DisplayCategory.FOOD_AND_HOUSEKEEPING,
    "bus pass": DisplayCategory.TRANSPORT,
    "train ticket": DisplayCategory.TRANSPORT,
    "fuel": DisplayCategory.TRANSPORT,
    "petrol": DisplayCategory.TRANSPORT,
    "prescriptions": DisplayCategory.HEALTH_AND_CARE,
    "dentist": DisplayCategory.HEALTH_AND_CARE,
    "childcare": DisplayCategory.CHILDREN_AND_DEPENDANTS,
    "nursery": DisplayCategory.CHILDREN_AND_DEPENDANTS,
    "child maintenance": DisplayCategory.CHILDREN_AND_DEPENDANTS,
    "mobile": DisplayCategory.COMMUNICATIONS,
    "broadband": DisplayCategory.COMMUNICATIONS,
    "mobile and broadband": DisplayCategory.COMMUNICATIONS,
    "home insurance": DisplayCategory.INSURANCE,
    "car insurance": DisplayCategory.INSURANCE,
    "credit card repayment": DisplayCategory.EXISTING_DEBT_REPAYMENTS,
    "loan repayment": DisplayCategory.EXISTING_DEBT_REPAYMENTS,
    "catalogue repayment": DisplayCategory.EXISTING_DEBT_REPAYMENTS,
    "gym": DisplayCategory.LEISURE_AND_HOBBIES,
    "streaming subscription": DisplayCategory.LEISURE_AND_HOBBIES,
    "savings": DisplayCategory.SAVINGS_AND_FUTURE_PROVISIONS,
    "emergency fund": DisplayCategory.SAVINGS_AND_FUTURE_PROVISIONS,
}

# Phrases that name a merchant or a movement of money rather than a purpose.
# Model confidence is irrelevant here: the business rule is that the customer
# says what these were for.
_AMBIGUOUS: frozenset[str] = frozenset(
    {
        "apple",
        "amazon",
        "google",
        "paypal",
        "transfer",
        "bank transfer",
        "payment",
        "direct debit",
        "standing order",
        "cash",
        "withdrawal",
        "misc",
        "miscellaneous",
        "other",
        "shopping",
        "subscription",
    }
)

_PUNCTUATION = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WHITESPACE = re.compile(r"\s+", flags=re.UNICODE)


def normalize_description(description: str) -> str:
    """Fold a reported description to a comparable phrase.

    Case, surrounding and repeated whitespace, punctuation, and compatibility
    Unicode forms are removed. The result is compared whole; it is never used
    for substring matching.
    """
    # NFKC folds full-width characters and similar compatibility forms; the
    # curly apostrophe is punctuation and is removed below.
    folded = unicodedata.normalize("NFKC", description)
    without_punctuation = _PUNCTUATION.sub(" ", folded)
    collapsed = _WHITESPACE.sub(" ", without_punctuation).strip()
    return collapsed.casefold()


@dataclass(frozen=True)
class CustomerPreference:
    """A rule the customer created by correcting a classification."""

    normalized_description: str
    display_category: DisplayCategory
    outgoing_treatment: OutgoingTreatment


@dataclass(frozen=True)
class ClassificationOutcome:
    normalized_description: str
    display_category: DisplayCategory | None
    outgoing_treatment: OutgoingTreatment | None
    source: ClassificationSource | None
    reason_code: str | None
    taxonomy_version: str = TAXONOMY_VERSION

    @property
    def is_resolved(self) -> bool:
        return self.source is not None

    @property
    def requires_confirmation(self) -> bool:
        return not self.is_resolved

    def confirmed_as(
        self,
        *,
        display_category: DisplayCategory,
        outgoing_treatment: OutgoingTreatment,
    ) -> "ClassificationOutcome":
        """Record what the customer accepted or corrected."""
        return replace(
            self,
            display_category=display_category,
            outgoing_treatment=outgoing_treatment,
            source=ClassificationSource.CUSTOMER_CONFIRMATION,
            reason_code=None,
        )

    def with_display_category(self, display_category: DisplayCategory) -> "ClassificationOutcome":
        """Change the category only.

        The treatment was confirmed independently and is deliberately left
        alone, because the customer's circumstances decided it.
        """
        return replace(self, display_category=display_category)

    def with_outgoing_treatment(
        self, outgoing_treatment: OutgoingTreatment
    ) -> "ClassificationOutcome":
        return replace(self, outgoing_treatment=outgoing_treatment)

    def as_preference(self) -> CustomerPreference:
        if self.display_category is None or self.outgoing_treatment is None:
            raise ValueError("an unresolved classification cannot become a preference")
        return CustomerPreference(
            normalized_description=self.normalized_description,
            display_category=self.display_category,
            outgoing_treatment=self.outgoing_treatment,
        )


def _unresolved(normalized: str, reason_code: str) -> ClassificationOutcome:
    return ClassificationOutcome(
        normalized_description=normalized,
        display_category=None,
        outgoing_treatment=None,
        source=None,
        reason_code=reason_code,
    )


def classify_outgoing(
    description: str,
    *,
    preferences: tuple[CustomerPreference, ...] = (),
) -> ClassificationOutcome:
    """Classify one reported outgoing without consulting any provider."""
    if not isinstance(description, str) or not description.strip():
        raise ValueError("outgoing description must not be blank")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(
            f"outgoing description must be {MAX_DESCRIPTION_LENGTH} characters or fewer"
        )

    normalized = normalize_description(description)
    if not normalized:
        raise ValueError("outgoing description must contain usable characters")

    # 1. The customer's own confirmed preference always wins.
    for preference in preferences:
        if preference.normalized_description == normalized:
            return ClassificationOutcome(
                normalized_description=normalized,
                display_category=preference.display_category,
                outgoing_treatment=preference.outgoing_treatment,
                source=ClassificationSource.CUSTOMER_PREFERENCE,
                reason_code=None,
            )

    # 2. Ambiguous phrases are checked before the rules so that a merchant name
    #    can never be resolved by a rule that happens to share its wording.
    if normalized in _AMBIGUOUS:
        return _unresolved(normalized, "description_ambiguous")

    # 3. Deterministic global rules, matched on the whole phrase.
    category = _RULES.get(normalized)
    if category is not None:
        return ClassificationOutcome(
            normalized_description=normalized,
            display_category=category,
            outgoing_treatment=default_treatment_for(category),
            source=ClassificationSource.DETERMINISTIC_RULE,
            reason_code=None,
        )

    # 4. Never guess.
    return _unresolved(normalized, "description_unknown")
