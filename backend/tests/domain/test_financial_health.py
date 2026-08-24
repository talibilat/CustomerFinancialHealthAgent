from decimal import Decimal

import pytest

from customer_financial_health_api.domain.financial_health import (
    CurrentPositionResultCode,
    Frequency,
    MoneyEntry,
    calculate_monthly_position,
    normalize_to_monthly,
)


def test_normalizes_a_monthly_amount_unchanged():
    assert normalize_to_monthly(Decimal("1500"), Frequency.MONTHLY) == Decimal("1500.00")


def test_normalizes_a_weekly_amount_using_52_over_12():
    # 100 * 52 / 12 = 433.3333... -> rounds to 433.33
    assert normalize_to_monthly(Decimal("100"), Frequency.WEEKLY) == Decimal("433.33")


def test_normalizes_a_fortnightly_amount_using_26_over_12():
    # 200 * 26 / 12 = 433.3333... -> rounds to 433.33
    assert normalize_to_monthly(Decimal("200"), Frequency.FORTNIGHTLY) == Decimal("433.33")


def test_normalizes_a_four_weekly_amount_using_13_over_12():
    # 100 * 13 / 12 = 108.3333... -> rounds to 108.33
    assert normalize_to_monthly(Decimal("100"), Frequency.FOUR_WEEKLY) == Decimal("108.33")


def test_normalizes_a_quarterly_amount_using_4_over_12():
    # 300 * 4 / 12 = 100.00
    assert normalize_to_monthly(Decimal("300"), Frequency.QUARTERLY) == Decimal("100.00")


def test_normalizes_an_annual_amount_using_divide_by_12():
    # 1200 / 12 = 100.00
    assert normalize_to_monthly(Decimal("1200"), Frequency.ANNUAL) == Decimal("100.00")


def test_monthly_position_reports_surplus_when_income_exceeds_outgoings():
    result = calculate_monthly_position(
        income_entries=[MoneyEntry(Decimal("1500"), Frequency.MONTHLY)],
        outgoing_entries=[MoneyEntry(Decimal("1000"), Frequency.MONTHLY)],
    )

    assert result.normalized_monthly_income == Decimal("1500.00")
    assert result.normalized_monthly_outgoings == Decimal("1000.00")
    assert result.monthly_headroom == Decimal("500.00")
    assert result.result_code == CurrentPositionResultCode.SURPLUS


def test_monthly_position_reports_shortfall_by_one_penny():
    result = calculate_monthly_position(
        income_entries=[MoneyEntry(Decimal("1000.00"), Frequency.MONTHLY)],
        outgoing_entries=[MoneyEntry(Decimal("1000.01"), Frequency.MONTHLY)],
    )

    assert result.monthly_headroom == Decimal("-0.01")
    assert result.result_code == CurrentPositionResultCode.SHORTFALL


def test_monthly_position_reports_balanced_at_exact_zero_headroom():
    result = calculate_monthly_position(
        income_entries=[MoneyEntry(Decimal("1000.00"), Frequency.MONTHLY)],
        outgoing_entries=[MoneyEntry(Decimal("1000.00"), Frequency.MONTHLY)],
    )

    assert result.monthly_headroom == Decimal("0.00")
    assert result.result_code == CurrentPositionResultCode.BALANCED


def test_monthly_position_with_zero_income_reports_shortfall_and_warning():
    result = calculate_monthly_position(
        income_entries=[],
        outgoing_entries=[MoneyEntry(Decimal("500.00"), Frequency.MONTHLY)],
    )

    assert result.normalized_monthly_income == Decimal("0.00")
    assert result.result_code == CurrentPositionResultCode.ZERO_INCOME
    assert "zero_income" in result.warnings


def test_monthly_position_with_no_income_or_outgoings_is_incomplete():
    result = calculate_monthly_position([], [])

    assert result.monthly_headroom == Decimal("0.00")
    assert result.result_code == CurrentPositionResultCode.INCOMPLETE_INFORMATION
    assert result.warnings == ("incomplete_information",)


def test_monthly_position_rejects_negative_income_amount():
    with pytest.raises(ValueError):
        calculate_monthly_position(
            income_entries=[MoneyEntry(Decimal("-100"), Frequency.MONTHLY)],
            outgoing_entries=[],
        )


def test_monthly_position_rejects_negative_outgoing_amount():
    with pytest.raises(ValueError):
        calculate_monthly_position(
            income_entries=[],
            outgoing_entries=[MoneyEntry(Decimal("-1"), Frequency.MONTHLY)],
        )
