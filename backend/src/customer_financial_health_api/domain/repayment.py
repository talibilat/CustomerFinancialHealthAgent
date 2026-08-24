"""Exploring a repayment scenario against an unchanged basis snapshot.

This module compares arithmetic with the customer's own protected monthly
buffer. It does not recommend an amount, does not know what the customer could
afford, and never treats savings or a protected reserve as monthly repayment
capacity - it cannot, because it is never given them.

The scenario is a comparison only. Nothing here writes anything.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

SCENARIO_POLICY_VERSION = "scenario-policy-v1"

ZERO = Decimal("0.00")

# The largest repayment this product will model, matching the statement's own
# ceiling so a scenario cannot be built from an amount a statement would refuse.
MAX_REPAYMENT = Decimal("999999.99")


class ScenarioMode(str, Enum):
    #: Keep every existing commitment and add one more repayment.
    ADDITIONAL = "additional"
    #: Replace one selected existing commitment with a different amount.
    CHANGE_EXISTING = "change_existing"


class ScenarioResultCode(str, Enum):
    NOT_ENOUGH_REPORTED_HEADROOM = "not_enough_reported_headroom"
    MAY_LEAVE_LIMITED_ROOM = "may_leave_limited_room"
    #: Deliberately qualified. Positive arithmetic is evidence, not proof.
    APPEARS_MANAGEABLE = "appears_manageable_from_the_information_provided"


@dataclass(frozen=True)
class ScenarioResult:
    calculation_policy_version: str
    mode: ScenarioMode
    basis_monthly_headroom: Decimal
    proposed_repayment: Decimal
    replaced_repayment: Decimal | None
    scenario_headroom: Decimal
    protected_monthly_buffer: Decimal | None
    #: How far below the customer's buffer the scenario lands, when they gave one.
    buffer_shortfall: Decimal | None
    result_code: ScenarioResultCode
    warnings: tuple[str, ...]


def _reject_negative(amount: Decimal | None, label: str) -> None:
    if amount is not None and amount < 0:
        raise ValueError(f"{label} must not be negative: {amount}")


def calculate_scenario(
    *,
    monthly_headroom: Decimal,
    mode: ScenarioMode,
    proposed_repayment: Decimal,
    replaced_repayment: Decimal | None = None,
    protected_monthly_buffer: Decimal | None = None,
) -> ScenarioResult:
    """Compare one hypothetical repayment with the reported monthly position.

    ``monthly_headroom`` comes from the basis snapshot and is never modified.
    Savings and reserves are deliberately not parameters: they are resilience,
    not recurring capacity, so they cannot leak into this calculation.
    """
    _reject_negative(proposed_repayment, "proposed repayment")
    _reject_negative(replaced_repayment, "replaced repayment")
    _reject_negative(protected_monthly_buffer, "protected monthly buffer")

    if proposed_repayment == 0:
        # Zero is the customer's current position, not a scenario. Saying so is
        # clearer than showing a comparison that changes nothing.
        raise ValueError("a repayment scenario needs an amount above zero")
    if proposed_repayment > MAX_REPAYMENT:
        raise ValueError(f"proposed repayment must be {MAX_REPAYMENT} or less")

    if mode is ScenarioMode.CHANGE_EXISTING and replaced_repayment is None:
        raise ValueError("changing an existing repayment needs the commitment being replaced")
    if mode is ScenarioMode.ADDITIONAL:
        # Nothing is removed: the basis headroom already contains every
        # commitment the customer reported.
        replaced_repayment = None

    freed = replaced_repayment if replaced_repayment is not None else ZERO
    scenario_headroom = monthly_headroom + freed - proposed_repayment

    warnings: list[str] = []
    buffer_shortfall: Decimal | None = None

    if scenario_headroom < 0:
        result_code = ScenarioResultCode.NOT_ENOUGH_REPORTED_HEADROOM
    elif protected_monthly_buffer is None:
        # Without the customer's own buffer there is no threshold to judge
        # against, and inventing one would be a fabricated standard.
        warnings.append("protected_buffer_missing")
        result_code = ScenarioResultCode.MAY_LEAVE_LIMITED_ROOM
    elif scenario_headroom >= protected_monthly_buffer:
        # Inclusive: meeting the buffer exactly counts as meeting it.
        result_code = ScenarioResultCode.APPEARS_MANAGEABLE
    else:
        buffer_shortfall = protected_monthly_buffer - scenario_headroom
        result_code = ScenarioResultCode.MAY_LEAVE_LIMITED_ROOM

    if monthly_headroom <= 0:
        warnings.append("no_reported_headroom_before_this_repayment")

    return ScenarioResult(
        calculation_policy_version=SCENARIO_POLICY_VERSION,
        mode=mode,
        basis_monthly_headroom=monthly_headroom,
        proposed_repayment=proposed_repayment,
        replaced_repayment=replaced_repayment,
        scenario_headroom=scenario_headroom,
        protected_monthly_buffer=protected_monthly_buffer,
        buffer_shortfall=buffer_shortfall,
        result_code=result_code,
        warnings=tuple(warnings),
    )
