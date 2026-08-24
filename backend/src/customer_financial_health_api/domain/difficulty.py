"""Deterministic financial-difficulty states and support routes.

The interface accepts calculated facts only.
It owns the fixed customer copy and route selection so neither an HTTP adapter
nor an optional AI provider can change when support appears.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from customer_financial_health_api.domain.financial_health import MonthlyPositionResult


class DifficultyResultCode(str, Enum):
    NO_DIFFICULTY_IDENTIFIED = "no_difficulty_identified"
    INCOMPLETE_INFORMATION = "incomplete_information"
    ZERO_INCOME = "zero_income"
    REPORTED_SHORTFALL = "reported_shortfall"
    PROTECTED_OUTGOINGS_NOT_COVERED = "protected_outgoings_not_covered"


class SupportRouteCode(str, Enum):
    REVIEW_INFORMATION = "review_information"
    CONTACT_OPHELOS = "contact_ophelos"
    MONEYHELPER_DEBT_ADVICE = "moneyhelper_debt_advice"


@dataclass(frozen=True)
class SupportRoute:
    code: SupportRouteCode
    label: str
    description: str
    url: str
    external: bool = False


@dataclass(frozen=True)
class DifficultyAssessment:
    result_code: DifficultyResultCode
    title: str
    explanation: str
    shortfall: Decimal | None
    protected_monthly_outgoings: Decimal
    warnings: tuple[str, ...]
    support_routes: tuple[SupportRoute, ...]


REVIEW_INFORMATION = SupportRoute(
    code=SupportRouteCode.REVIEW_INFORMATION,
    label="Review your information",
    description="Check the income and outgoings you reported and update anything that has changed.",
    url="/statement",
)
CONTACT_OPHELOS = SupportRoute(
    code=SupportRouteCode.CONTACT_OPHELOS,
    label="Contact Ophelos support",
    description="Talk to our support team placeholder about your circumstances and the options available.",
    url="mailto:support@example.ophelos.com",
)
MONEYHELPER_DEBT_ADVICE = SupportRoute(
    code=SupportRouteCode.MONEYHELPER_DEBT_ADVICE,
    label="Find free independent debt advice",
    description="Use MoneyHelper's official Debt Advice Locator to find confidential, independent support.",
    url="https://www.moneyhelper.org.uk/en/money-troubles/dealing-with-debt/debt-advice-locator",
    external=True,
)

DIFFICULTY_SUPPORT = (
    REVIEW_INFORMATION,
    CONTACT_OPHELOS,
    MONEYHELPER_DEBT_ADVICE,
)


def _gbp(amount: Decimal) -> str:
    return f"£{amount:,.2f}"


def assess_financial_difficulty(
    position: MonthlyPositionResult,
    protected_monthly_outgoings: Decimal,
) -> DifficultyAssessment:
    """Select one result and its support from deterministic calculated facts."""
    income = position.normalized_monthly_income
    outgoings = position.normalized_monthly_outgoings
    shortfall = -position.monthly_headroom if position.monthly_headroom < 0 else None

    if income == 0 and outgoings == 0:
        return DifficultyAssessment(
            result_code=DifficultyResultCode.INCOMPLETE_INFORMATION,
            title="Add information to see your monthly position",
            explanation="No monthly income or outgoings are reported yet, so a current position cannot be shown.",
            shortfall=None,
            protected_monthly_outgoings=protected_monthly_outgoings,
            warnings=("incomplete_information",),
            support_routes=(REVIEW_INFORMATION,),
        )

    if income == 0:
        return DifficultyAssessment(
            result_code=DifficultyResultCode.ZERO_INCOME,
            title="No monthly income is reported",
            explanation=(
                f"The information reported shows a monthly shortfall of {_gbp(shortfall or Decimal('0.00'))}. "
                "This result does not divide by income. Support is available if you would like it."
            ),
            shortfall=shortfall,
            protected_monthly_outgoings=protected_monthly_outgoings,
            warnings=("zero_income", "reported_shortfall"),
            support_routes=DIFFICULTY_SUPPORT,
        )

    if protected_monthly_outgoings > income:
        return DifficultyAssessment(
            result_code=DifficultyResultCode.PROTECTED_OUTGOINGS_NOT_COVERED,
            title="Reported income does not cover protected outgoings",
            explanation=(
                f"Protected monthly outgoings are {_gbp(protected_monthly_outgoings)}, compared with "
                f"reported monthly income of {_gbp(income)}. Review the information or use a support route below."
            ),
            shortfall=shortfall,
            protected_monthly_outgoings=protected_monthly_outgoings,
            warnings=("protected_outgoings_not_covered", "reported_shortfall"),
            support_routes=DIFFICULTY_SUPPORT,
        )

    if shortfall is not None:
        return DifficultyAssessment(
            result_code=DifficultyResultCode.REPORTED_SHORTFALL,
            title="Reported outgoings are above income",
            explanation=(
                f"The information reported shows an exact monthly shortfall of {_gbp(shortfall)}. "
                "Every reported living cost remains part of this result, including costs whose amount may vary."
            ),
            shortfall=shortfall,
            protected_monthly_outgoings=protected_monthly_outgoings,
            warnings=("reported_shortfall",),
            support_routes=DIFFICULTY_SUPPORT,
        )

    return DifficultyAssessment(
        result_code=DifficultyResultCode.NO_DIFFICULTY_IDENTIFIED,
        title="No difficulty state identified from this monthly position",
        explanation="This reflects only the information reported for this statement period.",
        shortfall=None,
        protected_monthly_outgoings=protected_monthly_outgoings,
        warnings=(),
        support_routes=(),
    )
