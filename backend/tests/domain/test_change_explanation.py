from datetime import date
from decimal import Decimal

from customer_financial_health_api.domain.history import (
    PeriodTotals,
    ReportedComponent,
    explain_change,
)


def component(description, section, monthly):
    return ReportedComponent(description=description, section=section, monthly_amount=Decimal(monthly))


def totals(period, income, outgoings, components):
    return PeriodTotals(
        statement_period=date.fromisoformat(period),
        normalized_monthly_income=Decimal(income),
        normalized_monthly_outgoings=Decimal(outgoings),
        components=tuple(components),
    )


BASE = totals(
    "2026-07-01",
    "2450.00",
    "1500.00",
    [
        component("Wages", "income", "2450.00"),
        component("Rent", "outgoing", "950.00"),
        component("Food", "outgoing", "550.00"),
    ],
)


class TestBaseline:
    def test_the_first_snapshot_is_a_baseline_and_invents_no_trend(self):
        explanation = explain_change(previous=None, current=BASE)

        assert explanation.is_baseline
        assert explanation.monthly_headroom_change is None
        assert explanation.increases == ()
        assert explanation.decreases == ()
        assert "no_comparable_period" in explanation.warnings


class TestReconciliation:
    def test_signed_component_changes_sum_exactly_to_the_headroom_change(self):
        current = totals(
            "2026-08-01",
            "2600.00",
            "1580.00",
            [
                component("Wages", "income", "2600.00"),
                component("Rent", "outgoing", "1000.00"),
                component("Food", "outgoing", "580.00"),
            ],
        )

        explanation = explain_change(previous=BASE, current=current)

        assert explanation.monthly_headroom_change == Decimal("70.00")
        signed = sum(
            (c.signed_headroom_effect for c in explanation.increases + explanation.decreases),
            start=Decimal("0.00"),
        )
        assert signed == explanation.monthly_headroom_change

    def test_offsetting_changes_still_reconcile_and_are_both_reported(self):
        current = totals(
            "2026-08-01",
            "2450.00",
            "1500.00",
            [
                component("Wages", "income", "2450.00"),
                component("Rent", "outgoing", "1050.00"),
                component("Food", "outgoing", "450.00"),
            ],
        )

        explanation = explain_change(previous=BASE, current=current)

        assert explanation.monthly_headroom_change == Decimal("0.00")
        labels = {c.description for c in explanation.increases + explanation.decreases}
        assert labels == {"Rent", "Food"}
        signed = sum(
            (c.signed_headroom_effect for c in explanation.increases + explanation.decreases),
            start=Decimal("0.00"),
        )
        assert signed == Decimal("0.00")

    def test_identical_totals_with_different_categories_show_no_headroom_change(self):
        current = totals(
            "2026-08-01",
            "2450.00",
            "1500.00",
            [
                component("Wages", "income", "2450.00"),
                component("Rent", "outgoing", "950.00"),
                component("Groceries", "outgoing", "550.00"),
            ],
        )

        explanation = explain_change(previous=BASE, current=current)

        assert explanation.monthly_headroom_change == Decimal("0.00")
        # Food ended and Groceries began: both are visible, and they cancel out.
        labels = {c.description for c in explanation.increases + explanation.decreases}
        assert labels == {"Food", "Groceries"}
        signed = sum(
            (c.signed_headroom_effect for c in explanation.increases + explanation.decreases),
            start=Decimal("0.00"),
        )
        assert signed == Decimal("0.00")


class TestDirection:
    def test_more_income_helps_and_more_outgoings_hurt(self):
        current = totals(
            "2026-08-01",
            "2500.00",
            "1600.00",
            [
                component("Wages", "income", "2500.00"),
                component("Rent", "outgoing", "1050.00"),
                component("Food", "outgoing", "550.00"),
            ],
        )

        explanation = explain_change(previous=BASE, current=current)
        by_label = {c.description: c for c in explanation.increases + explanation.decreases}

        assert by_label["Wages"].signed_headroom_effect == Decimal("50.00")
        assert by_label["Rent"].signed_headroom_effect == Decimal("-100.00")

    def test_an_entry_that_stopped_is_reported_as_a_change(self):
        current = totals(
            "2026-08-01",
            "2450.00",
            "950.00",
            [
                component("Wages", "income", "2450.00"),
                component("Rent", "outgoing", "950.00"),
            ],
        )

        explanation = explain_change(previous=BASE, current=current)
        by_label = {c.description: c for c in explanation.increases + explanation.decreases}

        assert by_label["Food"].previous_monthly == Decimal("550.00")
        assert by_label["Food"].current_monthly == Decimal("0.00")
        assert by_label["Food"].signed_headroom_effect == Decimal("550.00")

    def test_unchanged_components_are_not_reported_as_changes(self):
        explanation = explain_change(previous=BASE, current=BASE)

        assert explanation.increases == ()
        assert explanation.decreases == ()
        assert explanation.monthly_headroom_change == Decimal("0.00")


class TestNoInferredCause:
    def test_the_explanation_carries_only_amounts_and_labels_the_customer_gave(self):
        current = totals(
            "2026-08-01",
            "0.00",
            "1500.00",
            [component("Rent", "outgoing", "950.00"), component("Food", "outgoing", "550.00")],
        )

        explanation = explain_change(previous=BASE, current=current)
        text = " ".join(
            f"{c.description} {c.section}" for c in explanation.increases + explanation.decreases
        )

        assert "job" not in text.lower()
        assert "because" not in text.lower()
        # The customer's own labels are all that appear.
        assert set(c.description for c in explanation.increases + explanation.decreases) <= {
            "Wages",
            "Rent",
            "Food",
        }


def test_a_decomposition_that_cannot_account_for_the_whole_move_says_so():
    """Stored line items that do not sum to the stored totals must not pass silently."""
    inconsistent = totals(
        "2026-08-01",
        "2450.00",
        "1500.00",
        # Deliberately missing Food, so the parts cannot explain the whole.
        [component("Wages", "income", "2450.00"), component("Rent", "outgoing", "950.00")],
    )

    explanation = explain_change(previous=BASE, current=inconsistent)

    assert "change_decomposition_incomplete" in explanation.warnings
