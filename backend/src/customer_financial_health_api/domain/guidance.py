"""Optional wording over approved deterministic facts.

This module is the sole authority for accepting provider wording. The provider
never receives customer identity, snapshot identity, raw line items, links, or
free-form history, and its output can never alter a result or support route.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import Mapping, Protocol

PROMPT_VERSION = "guidance-prompt-v1"
SCHEMA_VERSION = "guidance-schema-v1"
MAX_EXPLANATION_LENGTH = 900


class GuidanceRequestOutcome(str, Enum):
    GENERATED = "generated"
    FALLBACK_NOT_CONFIGURED = "fallback_not_configured"
    FALLBACK_PROVIDER_ERROR = "fallback_provider_error"
    FALLBACK_INVALID_OUTPUT = "fallback_invalid_output"


@dataclass(frozen=True)
class GuidanceChange:
    fact_key: str
    signed_headroom_effect: Decimal


@dataclass(frozen=True)
class GuidanceFacts:
    normalized_monthly_income: Decimal
    normalized_monthly_outgoings: Decimal
    monthly_headroom: Decimal
    result_code: str
    warning_codes: tuple[str, ...]
    support_codes: tuple[str, ...]
    resilience: Mapping[str, str | None] = field(default_factory=dict)
    deterministic_changes: tuple[GuidanceChange, ...] = ()

    def fact_amounts(self) -> dict[str, Decimal]:
        amounts = {
            "normalized_monthly_income": self.normalized_monthly_income,
            "normalized_monthly_outgoings": self.normalized_monthly_outgoings,
            "monthly_headroom": self.monthly_headroom,
        }
        for key, value in self.resilience.items():
            if value is not None:
                try:
                    amounts[f"resilience.{key}"] = Decimal(value)
                except InvalidOperation:
                    continue
        for change in self.deterministic_changes:
            amounts[f"change.{change.fact_key}"] = change.signed_headroom_effect
        return amounts

    def provider_payload(self) -> dict[str, object]:
        return {
            "normalized_monthly_income": _money(self.normalized_monthly_income),
            "normalized_monthly_outgoings": _money(self.normalized_monthly_outgoings),
            "monthly_headroom": _money(self.monthly_headroom),
            "result_code": self.result_code,
            "resilience": dict(self.resilience),
            "warning_codes": list(self.warning_codes),
            "support_codes": list(self.support_codes),
            "deterministic_changes": [
                {
                    "fact_key": change.fact_key,
                    "signed_headroom_effect": _money(change.signed_headroom_effect),
                }
                for change in self.deterministic_changes
            ],
            "wording_constraints": {
                "locale": "en-GB",
                "currency": "GBP",
                "maximum_characters": MAX_EXPLANATION_LENGTH,
                "plain_text_only": True,
                "no_advice_or_recommendations": True,
                "no_inferred_causes": True,
            },
        }


@dataclass(frozen=True)
class GuidanceOutcome:
    text: str
    outcome: GuidanceRequestOutcome
    deployment: str | None
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION


class GuidanceGenerator(Protocol):
    deployment: str

    def generate(self, facts: GuidanceFacts) -> object | None: ...


_ALLOWED_KEYS = frozenset(
    {
        "text",
        "result_code",
        "warning_codes",
        "support_codes",
        "referenced_fact_keys",
    }
)
_MONEY_TOKEN = re.compile(r"(?:-?£[\d,]+(?:\.\d{1,2})?|(?<![\w.-])-?\d+(?:\.\d+)?)")
_MARKUP_OR_LINK = re.compile(r"<[^>]*>|https?://|www\.|\[[^\]]+\]\([^)]*\)", re.IGNORECASE)
_EXECUTABLE = re.compile(r"(?:```|<script|javascript:|\b(?:curl|sudo|exec|eval)\s)", re.IGNORECASE)
_PROHIBITED = (
    "because you",
    "caused by",
    "due to",
    "you should",
    "you must",
    "i recommend",
    "we recommend",
    "repayment of",
    "repayment amount",
    "pay £",
    "reduce your",
    "cut your",
    "change the category",
    "buy this",
    "use this product",
    "affordable",
    "approved",
    "failed",
    "irresponsible",
    "bad with money",
    "overspending",
)


def _money(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}£{abs(value):,.2f}"


def deterministic_explanation(facts: GuidanceFacts) -> str:
    if facts.monthly_headroom < 0:
        position = f"a monthly shortfall of {_money(-facts.monthly_headroom)}"
    elif facts.monthly_headroom == 0:
        position = "no reported monthly headroom"
    else:
        position = f"{_money(facts.monthly_headroom)} of monthly headroom"
    return (
        f"Reported monthly income is {_money(facts.normalized_monthly_income)} and reported "
        f"monthly outgoings are {_money(facts.normalized_monthly_outgoings)}, leaving {position}. "
        "This is based on the information reported and is not proof of long-term affordability."
    )


def _safe_text(payload: object, facts: GuidanceFacts) -> str | None:
    if not isinstance(payload, Mapping) or set(payload) != _ALLOWED_KEYS:
        return None
    text = payload.get("text")
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text or len(text) > MAX_EXPLANATION_LENGTH or "\n" in text:
        return None
    if payload.get("result_code") != facts.result_code:
        return None
    if payload.get("warning_codes") != list(facts.warning_codes):
        return None
    if payload.get("support_codes") != list(facts.support_codes):
        return None
    referenced = payload.get("referenced_fact_keys")
    if not isinstance(referenced, list) or not all(isinstance(key, str) for key in referenced):
        return None
    allowed_facts = facts.fact_amounts()
    if not set(referenced) <= set(allowed_facts):
        return None
    if _MARKUP_OR_LINK.search(text) or _EXECUTABLE.search(text):
        return None
    lowered = text.casefold()
    if any(phrase in lowered for phrase in _PROHIBITED):
        return None
    allowed_numbers = {
        token
        for amount in allowed_facts.values()
        for token in (_money(amount), _money(amount).removeprefix("£"))
    }
    if any(token not in allowed_numbers for token in _MONEY_TOKEN.findall(text)):
        return None
    return text


def create_personalized_explanation(
    facts: GuidanceFacts, generator: GuidanceGenerator | None
) -> GuidanceOutcome:
    fallback = deterministic_explanation(facts)
    if generator is None:
        return GuidanceOutcome(
            text=fallback,
            outcome=GuidanceRequestOutcome.FALLBACK_NOT_CONFIGURED,
            deployment=None,
        )
    try:
        payload = generator.generate(facts)
    except Exception:
        return GuidanceOutcome(
            text=fallback,
            outcome=GuidanceRequestOutcome.FALLBACK_PROVIDER_ERROR,
            deployment=generator.deployment,
        )
    text = _safe_text(payload, facts)
    if text is None:
        return GuidanceOutcome(
            text=fallback,
            outcome=GuidanceRequestOutcome.FALLBACK_INVALID_OUTPUT,
            deployment=generator.deployment,
        )
    return GuidanceOutcome(
        text=text,
        outcome=GuidanceRequestOutcome.GENERATED,
        deployment=generator.deployment,
    )
