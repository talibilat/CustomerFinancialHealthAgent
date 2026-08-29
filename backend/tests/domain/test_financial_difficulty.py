from decimal import Decimal

import pytest

from customer_financial_health_api.domain.difficulty import (
    DifficultyResultCode,
    SupportRouteCode,
    assess_financial_difficulty,
)
from customer_financial_health_api.domain.financial_health import (
    Frequency,
    MoneyEntry,
    calculate_monthly_position,
)


@pytest.mark.parametrize(
    ("income", "outgoings", "protected", "code", "shortfall", "support"),
    [
        ("0.00", "500.25", "400.00", DifficultyResultCode.ZERO_INCOME, "500.25", 3),
        ("0.00", "0.00", "0.00", DifficultyResultCode.INCOMPLETE_INFORMATION, None, 1),
        ("1000.00", "1000.01", "800.00", DifficultyResultCode.REPORTED_SHORTFALL, "0.01", 3),
        (
            "1000.00",
            "1200.00",
            "1100.00",
            DifficultyResultCode.PROTECTED_OUTGOINGS_NOT_COVERED,
            "200.00",
            3,
        ),
        ("1500.00", "1000.00", "700.00", DifficultyResultCode.NO_DIFFICULTY_IDENTIFIED, None, 0),
    ],
)
def test_difficulty_state_selects_exact_amounts_and_support_routes(
    income, outgoings, protected, code, shortfall, support
):
    position = calculate_monthly_position(
        [MoneyEntry(Decimal(income), Frequency.MONTHLY)] if Decimal(income) else [],
        [MoneyEntry(Decimal(outgoings), Frequency.MONTHLY)] if Decimal(outgoings) else [],
    )

    result = assess_financial_difficulty(position, Decimal(protected))

    assert result.result_code is code
    assert (str(result.shortfall) if result.shortfall is not None else None) == shortfall
    assert len(result.support_routes) == support


def test_support_routes_are_fixed_and_safe_for_a_reported_shortfall():
    position = calculate_monthly_position(
        [MoneyEntry(Decimal("1000.00"), Frequency.MONTHLY)],
        [MoneyEntry(Decimal("1200.00"), Frequency.MONTHLY)],
    )

    result = assess_financial_difficulty(position, Decimal("600.00"))

    assert [route.code for route in result.support_routes] == [
        SupportRouteCode.REVIEW_INFORMATION,
        SupportRouteCode.CONTACT_OPHELOS,
        SupportRouteCode.MONEYHELPER_DEBT_ADVICE,
    ]
    assert result.support_routes[-1].url == "https://www.moneyhelper.org.uk/en/money-troubles/dealing-with-debt/debt-advice-locator"
    assert result.support_routes[1].url == "https://www.ophelos.com/contact"
    combined_copy = " ".join(
        [result.title, result.explanation]
        + [route.label + " " + route.description for route in result.support_routes]
    ).lower()
    for unsafe_phrase in ("failed", "afford", "must pay", "act now", "congratulations", "disposable"):
        assert unsafe_phrase not in combined_copy
    assert "placeholder" not in combined_copy


def test_protected_outgoings_take_precedence_over_general_shortfall_copy():
    position = calculate_monthly_position(
        [MoneyEntry(Decimal("900.00"), Frequency.MONTHLY)],
        [MoneyEntry(Decimal("1200.00"), Frequency.MONTHLY)],
    )

    result = assess_financial_difficulty(position, Decimal("950.00"))

    assert result.result_code is DifficultyResultCode.PROTECTED_OUTGOINGS_NOT_COVERED
    assert "£950.00" in result.explanation
    assert "£900.00" in result.explanation
    assert "repayment" not in result.explanation.lower()
