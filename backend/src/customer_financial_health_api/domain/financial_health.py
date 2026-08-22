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


class ResilienceResultCode(str, Enum):
    BELOW_RESERVE = "below_reserve"
    AT_RESERVE = "at_reserve"
    ABOVE_RESERVE = "above_reserve"


@dataclass(frozen=True)
class ResilienceResult:
    accessible_savings: Decimal | None
    protected_reserve: Decimal | None
    current_account_balance: Decimal | None
    known_arrears: Decimal | None
    savings_above_reserve: Decimal | None
    reserve_gap: Decimal | None
    result_code: ResilienceResultCode | None
    warnings: tuple[str, ...]


def calculate_resilience(
    accessible_savings: Decimal | None = None,
    protected_reserve: Decimal | None = None,
    current_account_balance: Decimal | None = None,
    known_arrears: Decimal | None = None,
) -> ResilienceResult:
    if accessible_savings is not None and accessible_savings < 0:
        raise ValueError(f"accessible savings must not be negative: {accessible_savings}")
    if protected_reserve is not None and protected_reserve < 0:
        raise ValueError(f"protected reserve must not be negative: {protected_reserve}")
    if known_arrears is not None and known_arrears < 0:
        raise ValueError(f"known arrears must not be negative: {known_arrears}")

    if accessible_savings is None or protected_reserve is None:
        return ResilienceResult(
            accessible_savings=accessible_savings,
            protected_reserve=protected_reserve,
            current_account_balance=current_account_balance,
            known_arrears=known_arrears,
            savings_above_reserve=None,
            reserve_gap=None,
            result_code=None,
            warnings=("resilience_info_missing",),
        )

    savings_above_reserve = max(Decimal("0.00"), accessible_savings - protected_reserve)
    reserve_gap = max(Decimal("0.00"), protected_reserve - accessible_savings)

    if accessible_savings < protected_reserve:
        result_code = ResilienceResultCode.BELOW_RESERVE
    elif accessible_savings == protected_reserve:
        result_code = ResilienceResultCode.AT_RESERVE
    else:
        result_code = ResilienceResultCode.ABOVE_RESERVE

    return ResilienceResult(
        accessible_savings=accessible_savings,
        protected_reserve=protected_reserve,
        current_account_balance=current_account_balance,
        known_arrears=known_arrears,
        savings_above_reserve=savings_above_reserve,
        reserve_gap=reserve_gap,
        result_code=result_code,
        warnings=(),
    )
