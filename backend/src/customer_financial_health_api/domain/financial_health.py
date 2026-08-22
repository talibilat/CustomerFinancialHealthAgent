from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Sequence

TWO_PLACES = Decimal("0.01")

NORMALIZATION_POLICY_VERSION = "normalization-policy-v1"

_MONTHLY_MULTIPLIER = {
    "weekly": Decimal("52") / Decimal("12"),
    "fortnightly": Decimal("26") / Decimal("12"),
    "four_weekly": Decimal("13") / Decimal("12"),
    "monthly": Decimal("1"),
    "quarterly": Decimal("4") / Decimal("12"),
    "annual": Decimal("1") / Decimal("12"),
}


class Frequency(str, Enum):
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    FOUR_WEEKLY = "four_weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


def normalize_to_monthly(amount: Decimal, frequency: Frequency) -> Decimal:
    monthly = amount * _MONTHLY_MULTIPLIER[frequency.value]
    return monthly.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class CurrentPositionResultCode(str, Enum):
    SURPLUS = "surplus"
    BALANCED = "balanced"
    SHORTFALL = "shortfall"


@dataclass(frozen=True)
class MoneyEntry:
    amount: Decimal
    frequency: Frequency


@dataclass(frozen=True)
class MonthlyPositionResult:
    calculation_policy_version: str
    normalized_monthly_income: Decimal
    normalized_monthly_outgoings: Decimal
    monthly_headroom: Decimal
    result_code: CurrentPositionResultCode
    warnings: tuple[str, ...]


def _result_code_for(headroom: Decimal) -> CurrentPositionResultCode:
    if headroom > 0:
        return CurrentPositionResultCode.SURPLUS
    if headroom == 0:
        return CurrentPositionResultCode.BALANCED
    return CurrentPositionResultCode.SHORTFALL


def _reject_negative_amounts(entries: Sequence[MoneyEntry], label: str) -> None:
    for entry in entries:
        if entry.amount < 0:
            raise ValueError(f"{label} amount must not be negative: {entry.amount}")


def calculate_monthly_position(
    income_entries: Sequence[MoneyEntry],
    outgoing_entries: Sequence[MoneyEntry],
) -> MonthlyPositionResult:
    _reject_negative_amounts(income_entries, "income")
    _reject_negative_amounts(outgoing_entries, "outgoing")

    normalized_income = sum(
        (normalize_to_monthly(entry.amount, entry.frequency) for entry in income_entries),
        start=Decimal("0.00"),
    )
    normalized_outgoings = sum(
        (normalize_to_monthly(entry.amount, entry.frequency) for entry in outgoing_entries),
        start=Decimal("0.00"),
    )
    headroom = normalized_income - normalized_outgoings

    warnings: list[str] = []
    if normalized_income == 0:
        warnings.append("zero_income")

    return MonthlyPositionResult(
        calculation_policy_version=NORMALIZATION_POLICY_VERSION,
        normalized_monthly_income=normalized_income,
        normalized_monthly_outgoings=normalized_outgoings,
        monthly_headroom=headroom,
        result_code=_result_code_for(headroom),
        warnings=tuple(warnings),
    )
