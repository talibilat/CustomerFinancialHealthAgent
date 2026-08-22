from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MoneyEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_amount: str
    original_frequency: str
    normalized_monthly_amount: str


class ResilienceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accessible_savings: str | None
    protected_reserve: str | None
    current_account_balance: str | None
    known_arrears: str | None
    savings_above_reserve: str | None
    reserve_gap: str | None
    result_code: str | None
    warnings: list[str]


class OverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    statement_period: date
    confirmed_at: datetime
    calculation_policy_version: str
    normalized_monthly_income: str
    normalized_monthly_outgoings: str
    monthly_headroom: str
    result_code: str
    warnings: list[str]
    income_entries: list[MoneyEntryOut]
    outgoing_entries: list[MoneyEntryOut]
    resilience: ResilienceOut
