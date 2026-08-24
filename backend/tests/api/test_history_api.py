from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from customer_financial_health_api.domain.classification import classify_outgoing
from customer_financial_health_api.domain.financial_health import (
    Frequency,
    calculate_monthly_position,
    calculate_resilience,
)
from customer_financial_health_api.domain.statement import StatementEntry
from customer_financial_health_api.persistence.repository import (
    create_customer,
    save_confirmed_snapshot,
)


def confirm(session, customer, period, day, *, income="2450.00", rent="950.00"):
    income_entries = [StatementEntry("i1", "Wages", Decimal(income), Frequency.MONTHLY)]
    outgoing_entries = [StatementEntry("o1", "Rent", Decimal(rent), Frequency.MONTHLY)]
    return save_confirmed_snapshot(
        session,
        customer_id=customer.id,
        statement_period=date.fromisoformat(period),
        confirmed_at=datetime(2026, 9, day, 9, 0, tzinfo=timezone.utc),
        position=calculate_monthly_position(
            [e.as_money_entry() for e in income_entries],
            [e.as_money_entry() for e in outgoing_entries],
        ),
        income_entries=income_entries,
        outgoing_entries=outgoing_entries,
        resilience=calculate_resilience(),
        classifications={"o1": classify_outgoing("Rent", preferences=())},
    )


@pytest.fixture()
def with_history(client, db_session):
    customer = create_customer(db_session)
    confirm(db_session, customer, "2026-07-01", 1)
    confirm(db_session, customer, "2026-08-01", 2, income="2600.00", rent="1000.00")
    db_session.commit()
    return client


@pytest.fixture()
def with_one_snapshot(client, db_session):
    customer = create_customer(db_session)
    confirm(db_session, customer, "2026-08-01", 1)
    db_session.commit()
    return client


class TestEmptyHistory:
    def test_no_customer_data_is_not_an_error(self, client, db_session):
        response = client.get("/history")

        assert response.status_code == 200
        body = response.json()
        assert body["snapshots"] == []
        assert body["series"] == []
        assert body["total"] == 0
        assert body["latest_change"] is None


class TestHistoryContent:
    def test_history_returns_a_closed_schema(self, with_history):
        body = with_history.get("/history").json()

        assert set(body.keys()) == {"total", "limit", "offset", "snapshots", "series", "latest_change"}
        assert set(body["snapshots"][0].keys()) == {
            "snapshot_id",
            "statement_period",
            "confirmed_at",
            "calculation_policy_version",
            "normalized_monthly_income",
            "normalized_monthly_outgoings",
            "monthly_headroom",
            "result_code",
            "warnings",
            "income_entries",
            "outgoing_entries",
        }

    def test_history_is_newest_period_first_with_exact_values(self, with_history):
        body = with_history.get("/history").json()

        assert [s["statement_period"] for s in body["snapshots"]] == ["2026-08-01", "2026-07-01"]
        assert body["snapshots"][0]["monthly_headroom"] == "1600.00"
        assert body["snapshots"][1]["monthly_headroom"] == "1500.00"

    def test_the_series_reads_oldest_first_for_a_chart_or_table(self, with_history):
        body = with_history.get("/history").json()

        assert [p["statement_period"] for p in body["series"]] == ["2026-07-01", "2026-08-01"]
        assert body["series"][0]["monthly_headroom"] == "1500.00"

    def test_stored_labels_and_categories_come_back_unchanged(self, with_history):
        entry = with_history.get("/history").json()["snapshots"][0]["outgoing_entries"][0]

        assert entry["description"] == "Rent"
        assert entry["classification"]["display_category"] == "housing"


class TestChangeExplanation:
    def test_the_latest_change_decomposes_and_reconciles(self, with_history):
        change = with_history.get("/history").json()["latest_change"]

        assert change["is_baseline"] is False
        assert change["previous_period"] == "2026-07-01"
        assert change["current_period"] == "2026-08-01"
        assert change["monthly_headroom_change"] == "100.00"

        signed = sum(
            Decimal(c["signed_headroom_effect"])
            for c in change["increases"] + change["decreases"]
        )
        assert signed == Decimal("100.00")

    def test_increases_and_decreases_are_both_named(self, with_history):
        change = with_history.get("/history").json()["latest_change"]

        assert [c["description"] for c in change["increases"]] == ["Wages"]
        assert [c["description"] for c in change["decreases"]] == ["Rent"]

    def test_a_single_snapshot_is_a_baseline_with_no_invented_comparison(self, with_one_snapshot):
        change = with_one_snapshot.get("/history").json()["latest_change"]

        assert change["is_baseline"] is True
        assert change["monthly_headroom_change"] is None
        assert change["previous_period"] is None
        assert "no_comparable_period" in change["warnings"]


class TestPagination:
    def test_pagination_metadata_is_returned_and_ordering_is_stable(self, with_history):
        first = with_history.get("/history?limit=1&offset=0").json()
        second = with_history.get("/history?limit=1&offset=1").json()

        assert first["total"] == 2
        assert first["limit"] == 1
        assert first["offset"] == 0
        assert first["snapshots"][0]["statement_period"] == "2026-08-01"
        assert second["snapshots"][0]["statement_period"] == "2026-07-01"

    def test_a_page_past_the_end_is_empty_not_an_error(self, with_history):
        response = with_history.get("/history?limit=10&offset=99")

        assert response.status_code == 200
        assert response.json()["snapshots"] == []

    def test_the_change_explanation_is_unaffected_by_the_page_being_viewed(self, with_history):
        first = with_history.get("/history?limit=1&offset=0").json()
        second = with_history.get("/history?limit=1&offset=1").json()

        assert first["latest_change"] == second["latest_change"]
