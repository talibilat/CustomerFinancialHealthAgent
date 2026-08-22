from decimal import Decimal

import pytest

from customer_financial_health_api.domain.financial_health import (
    ResilienceResultCode,
    calculate_resilience,
)


def test_resilience_above_reserve():
    result = calculate_resilience(
        accessible_savings=Decimal("1000.00"),
        protected_reserve=Decimal("400.00"),
    )

    assert result.savings_above_reserve == Decimal("600.00")
    assert result.reserve_gap == Decimal("0.00")
    assert result.result_code == ResilienceResultCode.ABOVE_RESERVE


def test_resilience_below_reserve():
    result = calculate_resilience(
        accessible_savings=Decimal("300.00"),
        protected_reserve=Decimal("500.00"),
    )

    assert result.savings_above_reserve == Decimal("0.00")
    assert result.reserve_gap == Decimal("200.00")
    assert result.result_code == ResilienceResultCode.BELOW_RESERVE


def test_resilience_at_reserve():
    result = calculate_resilience(
        accessible_savings=Decimal("500.00"),
        protected_reserve=Decimal("500.00"),
    )

    assert result.savings_above_reserve == Decimal("0.00")
    assert result.reserve_gap == Decimal("0.00")
    assert result.result_code == ResilienceResultCode.AT_RESERVE


def test_resilience_allows_negative_current_account_balance_as_overdraft():
    result = calculate_resilience(
        accessible_savings=Decimal("500.00"),
        protected_reserve=Decimal("500.00"),
        current_account_balance=Decimal("-120.50"),
    )

    assert result.current_account_balance == Decimal("-120.50")
    assert result.result_code == ResilienceResultCode.AT_RESERVE


def test_resilience_missing_savings_produces_limitation_without_blocking():
    result = calculate_resilience(protected_reserve=Decimal("500.00"))

    assert result.result_code is None
    assert result.savings_above_reserve is None
    assert result.reserve_gap is None
    assert "resilience_info_missing" in result.warnings


def test_resilience_missing_reserve_produces_limitation_without_blocking():
    result = calculate_resilience(accessible_savings=Decimal("500.00"))

    assert result.result_code is None
    assert "resilience_info_missing" in result.warnings


def test_resilience_rejects_negative_accessible_savings():
    with pytest.raises(ValueError):
        calculate_resilience(accessible_savings=Decimal("-1"), protected_reserve=Decimal("0"))


def test_resilience_rejects_negative_protected_reserve():
    with pytest.raises(ValueError):
        calculate_resilience(accessible_savings=Decimal("0"), protected_reserve=Decimal("-1"))


def test_resilience_rejects_negative_known_arrears():
    with pytest.raises(ValueError):
        calculate_resilience(
            accessible_savings=Decimal("0"),
            protected_reserve=Decimal("0"),
            known_arrears=Decimal("-1"),
        )
