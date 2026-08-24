"""Deterministic explanation of what changed between two confirmed periods.

The decomposition is arithmetic, not narrative. It reports which reported
amounts moved and by how much, and its signed components reconcile exactly to
the change in monthly headroom. It never infers a cause: nothing here knows
why an amount changed, and nothing may guess.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

INCOME = "income"
OUTGOING = "outgoing"

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ReportedComponent:
    """One reported line, already normalized to a monthly amount."""

    description: str
    section: str
    monthly_amount: Decimal


@dataclass(frozen=True)
class PeriodTotals:
    statement_period: date
    normalized_monthly_income: Decimal
    normalized_monthly_outgoings: Decimal
    components: tuple[ReportedComponent, ...]

    @property
    def monthly_headroom(self) -> Decimal:
        return self.normalized_monthly_income - self.normalized_monthly_outgoings


@dataclass(frozen=True)
class ComponentChange:
    description: str
    section: str
    previous_monthly: Decimal
    current_monthly: Decimal
    # Positive when the change increased monthly headroom, negative when it
    # reduced it. More income helps; more outgoings hurt.
    signed_headroom_effect: Decimal


@dataclass(frozen=True)
class ChangeExplanation:
    is_baseline: bool
    previous_period: date | None
    current_period: date
    monthly_headroom_change: Decimal | None
    increases: tuple[ComponentChange, ...]
    decreases: tuple[ComponentChange, ...]
    warnings: tuple[str, ...]


def _by_key(components: Sequence[ReportedComponent]) -> dict[tuple[str, str], Decimal]:
    """Total each section's reported lines by their label.

    Two lines the customer gave the same label in the same section are summed
    rather than one shadowing the other.
    """
    totals: dict[tuple[str, str], Decimal] = {}
    for component in components:
        key = (component.section, component.description)
        totals[key] = totals.get(key, ZERO) + component.monthly_amount
    return totals


def explain_change(
    *, previous: PeriodTotals | None, current: PeriodTotals
) -> ChangeExplanation:
    """Explain the move from one confirmed period to the next.

    With no comparable previous period this is a baseline: it reports no trend
    and says so, rather than inventing a comparison.
    """
    if previous is None:
        return ChangeExplanation(
            is_baseline=True,
            previous_period=None,
            current_period=current.statement_period,
            monthly_headroom_change=None,
            increases=(),
            decreases=(),
            warnings=("no_comparable_period",),
        )

    before = _by_key(previous.components)
    after = _by_key(current.components)

    changes: list[ComponentChange] = []
    for section, description in sorted(set(before) | set(after)):
        was = before.get((section, description), ZERO)
        now = after.get((section, description), ZERO)
        if was == now:
            continue
        delta = now - was
        changes.append(
            ComponentChange(
                description=description,
                section=section,
                previous_monthly=was,
                current_monthly=now,
                # Income moves headroom with it; an outgoing moves it against.
                signed_headroom_effect=delta if section == INCOME else -delta,
            )
        )

    increases = tuple(
        sorted(
            (c for c in changes if c.signed_headroom_effect > 0),
            key=lambda c: -c.signed_headroom_effect,
        )
    )
    decreases = tuple(
        sorted(
            (c for c in changes if c.signed_headroom_effect < 0),
            key=lambda c: c.signed_headroom_effect,
        )
    )

    headroom_change = current.monthly_headroom - previous.monthly_headroom

    warnings: list[str] = []
    # The decomposition is only trustworthy if it accounts for the whole move.
    # A gap means the stored line items do not sum to the stored totals.
    reconciled = sum((c.signed_headroom_effect for c in changes), start=ZERO)
    if reconciled != headroom_change:
        warnings.append("change_decomposition_incomplete")

    return ChangeExplanation(
        is_baseline=False,
        previous_period=previous.statement_period,
        current_period=current.statement_period,
        monthly_headroom_change=headroom_change,
        increases=increases,
        decreases=decreases,
        warnings=tuple(warnings),
    )
