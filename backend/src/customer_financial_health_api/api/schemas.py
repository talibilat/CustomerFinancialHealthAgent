from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


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


# --- Editable financial statement -------------------------------------------
#
# Request models are deliberately closed (extra="forbid") so customer
# identifiers, calculated results, and other mass-assignment attempts are
# rejected. Money and frequency arrive as plain strings so the domain, not
# Pydantic, produces the field-specific error the customer's form needs.


class StatementEntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str | None = None
    description: str
    amount: str
    frequency: str


class ExpectedChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str | None = None
    description: str
    kind: str
    amount: str
    frequency: str


class ResilienceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accessible_savings: str | None = None
    protected_reserve: str | None = None
    current_account_balance: str | None = None
    known_arrears: str | None = None


class LookingAheadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    irregular_costs: list[StatementEntryIn] = Field(default_factory=list)
    protected_future_provisions: list[StatementEntryIn] = Field(default_factory=list)
    expected_changes: list[ExpectedChangeIn] = Field(default_factory=list)


class StatementSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement_period: str
    currency: str = "GBP"
    income_entries: list[StatementEntryIn] = Field(default_factory=list)
    outgoing_entries: list[StatementEntryIn] = Field(default_factory=list)
    repayment_commitments: list[StatementEntryIn] = Field(default_factory=list)
    resilience: ResilienceIn = Field(default_factory=ResilienceIn)
    looking_ahead: LookingAheadIn = Field(default_factory=LookingAheadIn)


class StatementUpdateRequest(StatementSubmission):
    """A submission that replaces the stored statement it was built from."""

    # None only when the statement is being created for the first time.
    expected_version: int | None = None


class StatementEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    description: str
    original_amount: str
    original_frequency: str
    normalized_monthly_amount: str


class ExpectedChangeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    description: str
    kind: str
    original_amount: str
    original_frequency: str
    normalized_monthly_amount: str


class ResilienceSectionOut(BaseModel):
    """The resilience values the customer reported, not the calculated result."""

    model_config = ConfigDict(extra="forbid")

    accessible_savings: str | None
    protected_reserve: str | None
    current_account_balance: str | None
    known_arrears: str | None


class LookingAheadOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    irregular_costs: list[StatementEntryOut]
    protected_future_provisions: list[StatementEntryOut]
    expected_changes: list[ExpectedChangeOut]


class EditableStatementOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement_period: date
    currency: str
    income_entries: list[StatementEntryOut]
    outgoing_entries: list[StatementEntryOut]
    repayment_commitments: list[StatementEntryOut]
    resilience: ResilienceSectionOut
    looking_ahead: LookingAheadOut


class EditableStatementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    updated_at: datetime
    statement: EditableStatementOut


class StatementPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calculation_policy_version: str
    normalized_monthly_income: str
    normalized_monthly_outgoings: str
    monthly_headroom: str
    result_code: str
    warnings: list[str]
    normalized_monthly_repayment_commitments: str
    normalized_monthly_irregular_costs: str
    normalized_monthly_protected_future_provisions: str
    expected_changes: list[ExpectedChangeOut]
    resilience: ResilienceOut


class FieldErrorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    code: str
    message: str
