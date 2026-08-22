from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MoneyEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_amount: str
    original_frequency: str
    normalized_monthly_amount: str


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
