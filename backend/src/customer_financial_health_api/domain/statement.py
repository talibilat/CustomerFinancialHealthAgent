"""Validation and preview for the customer's editable financial statement.

This module owns every rule that decides whether a reported value is usable,
so the HTTP layer never has to interpret money, frequencies, or currencies.
Validation collects *all* field errors rather than stopping at the first, so
the customer can correct a whole form in one pass.

Preview is a pure recalculation from a submitted statement. It never reads or
writes a confirmed snapshot.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping, Sequence

from customer_financial_health_api.domain.financial_health import (
    NORMALIZATION_POLICY_VERSION,
    Frequency,
    MoneyEntry,
    MonthlyPositionResult,
    ResilienceResult,
    calculate_monthly_position,
    calculate_resilience,
    normalize_to_monthly,
)

SUPPORTED_CURRENCY = "GBP"

# The largest single amount the product accepts. This sits well inside the
# NUMERIC(12, 2) money columns so an over-large value is refused with a field
# error rather than reaching the database and failing there.
MAX_MONEY_AMOUNT = Decimal("999999.99")

MONEY_EXPONENT = Decimal("0.01")

# Reported statement periods outside this range are refused rather than stored.
EARLIEST_STATEMENT_PERIOD = date(2000, 1, 1)
LATEST_STATEMENT_PERIOD = date(2100, 1, 1)


class ExpectedChangeKind(str, Enum):
    INCOME_INCREASE = "income_increase"
    INCOME_DECREASE = "income_decrease"
    EXPENDITURE_INCREASE = "expenditure_increase"
    EXPENDITURE_DECREASE = "expenditure_decrease"


@dataclass(frozen=True)
class FieldError:
    """One invalid field, addressed by the path the customer's form uses."""

    field: str
    code: str
    message: str


class StatementValidationError(Exception):
    """Raised when a submitted statement contains one or more unusable fields."""

    def __init__(self, errors: Sequence[FieldError]):
        self.errors: tuple[FieldError, ...] = tuple(errors)
        super().__init__(f"{len(self.errors)} invalid field(s) in the submitted financial statement")


@dataclass(frozen=True)
class StatementEntry:
    entry_id: str
    description: str
    amount: Decimal
    frequency: Frequency

    @property
    def normalized_monthly_amount(self) -> Decimal:
        return normalize_to_monthly(self.amount, self.frequency)

    def as_money_entry(self) -> MoneyEntry:
        return MoneyEntry(amount=self.amount, frequency=self.frequency)


@dataclass(frozen=True)
class ExpectedChange:
    entry_id: str
    description: str
    kind: ExpectedChangeKind
    amount: Decimal
    frequency: Frequency

    @property
    def normalized_monthly_amount(self) -> Decimal:
        return normalize_to_monthly(self.amount, self.frequency)


@dataclass(frozen=True)
class ResilienceInput:
    accessible_savings: Decimal | None = None
    protected_reserve: Decimal | None = None
    current_account_balance: Decimal | None = None
    known_arrears: Decimal | None = None

    @property
    def is_empty(self) -> bool:
        return all(
            value is None
            for value in (
                self.accessible_savings,
                self.protected_reserve,
                self.current_account_balance,
                self.known_arrears,
            )
        )


@dataclass(frozen=True)
class LookingAheadInput:
    irregular_costs: tuple[StatementEntry, ...] = ()
    protected_future_provisions: tuple[StatementEntry, ...] = ()
    expected_changes: tuple[ExpectedChange, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.irregular_costs or self.protected_future_provisions or self.expected_changes)


@dataclass(frozen=True)
class FinancialStatement:
    statement_period: date
    income_entries: tuple[StatementEntry, ...]
    outgoing_entries: tuple[StatementEntry, ...]
    repayment_commitments: tuple[StatementEntry, ...]
    resilience: ResilienceInput = ResilienceInput()
    looking_ahead: LookingAheadInput = LookingAheadInput()
    currency: str = SUPPORTED_CURRENCY


@dataclass(frozen=True)
class StatementPreview:
    calculation_policy_version: str
    position: MonthlyPositionResult
    resilience: ResilienceResult
    normalized_monthly_repayment_commitments: Decimal
    normalized_monthly_irregular_costs: Decimal
    normalized_monthly_protected_future_provisions: Decimal
    expected_changes: tuple[ExpectedChange, ...]
    warnings: tuple[str, ...]


def _parse_money(
    raw: Any,
    field: str,
    errors: list[FieldError],
    *,
    allow_negative: bool = False,
) -> Decimal | None:
    """Parse one reported amount, appending at most one error for its field."""
    if raw is None:
        errors.append(FieldError(field, "amount_missing", "Enter an amount."))
        return None

    # bool is a subclass of int, and True would otherwise silently become 1.
    if isinstance(raw, bool) or not isinstance(raw, (str, int, Decimal)):
        errors.append(FieldError(field, "amount_not_a_number", "Enter an amount as a number."))
        return None

    text = str(raw).strip()
    if not text:
        errors.append(FieldError(field, "amount_blank", "Enter an amount."))
        return None

    try:
        value = Decimal(text)
    except InvalidOperation:
        errors.append(
            FieldError(field, "amount_not_a_number", "Enter an amount using digits and a decimal point.")
        )
        return None

    # Decimal accepts "NaN" and "Infinity" as valid literals.
    if not value.is_finite():
        errors.append(FieldError(field, "amount_not_finite", "Enter a real amount."))
        return None

    if -value.as_tuple().exponent > 2:
        errors.append(FieldError(field, "amount_too_precise", "Enter an amount in pounds and pence."))
        return None

    if not allow_negative and value < 0:
        errors.append(FieldError(field, "amount_negative", "Enter an amount of zero or more."))
        return None

    if abs(value) > MAX_MONEY_AMOUNT:
        errors.append(
            FieldError(field, "amount_above_maximum", f"Enter an amount of {MAX_MONEY_AMOUNT} or less.")
        )
        return None

    return value.quantize(MONEY_EXPONENT)


def _parse_frequency(raw: Any, field: str, errors: list[FieldError]) -> Frequency | None:
    try:
        return Frequency(raw)
    except (ValueError, TypeError):
        errors.append(FieldError(field, "frequency_not_supported", "Choose one of the supported frequencies."))
        return None


def _parse_text(raw: Any, field: str, errors: list[FieldError], *, max_length: int = 200) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        errors.append(FieldError(field, "text_blank", "Enter a short description."))
        return None
    text = raw.strip()
    if len(text) > max_length:
        errors.append(
            FieldError(field, "text_too_long", f"Use {max_length} characters or fewer.")
        )
        return None
    return text


def _parse_entries(raw: Any, prefix: str, errors: list[FieldError]) -> tuple[StatementEntry, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        errors.append(FieldError(prefix, "entries_not_a_list", "Provide a list of entries."))
        return ()

    entries: list[StatementEntry] = []
    for index, item in enumerate(raw):
        field_prefix = f"{prefix}.{index}"
        if not isinstance(item, Mapping):
            errors.append(FieldError(field_prefix, "entry_malformed", "Provide an entry with an amount."))
            continue

        description = _parse_text(item.get("description"), f"{field_prefix}.description", errors)
        amount = _parse_money(item.get("amount"), f"{field_prefix}.amount", errors)
        frequency = _parse_frequency(item.get("frequency"), f"{field_prefix}.frequency", errors)

        if description is None or amount is None or frequency is None:
            continue

        entries.append(
            StatementEntry(
                entry_id=str(item.get("entry_id") or f"{prefix}-{index}"),
                description=description,
                amount=amount,
                frequency=frequency,
            )
        )

    return tuple(entries)


def _parse_expected_changes(raw: Any, prefix: str, errors: list[FieldError]) -> tuple[ExpectedChange, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        errors.append(FieldError(prefix, "entries_not_a_list", "Provide a list of expected changes."))
        return ()

    changes: list[ExpectedChange] = []
    for index, item in enumerate(raw):
        field_prefix = f"{prefix}.{index}"
        if not isinstance(item, Mapping):
            errors.append(FieldError(field_prefix, "entry_malformed", "Provide an expected change."))
            continue

        description = _parse_text(item.get("description"), f"{field_prefix}.description", errors)

        kind: ExpectedChangeKind | None
        try:
            kind = ExpectedChangeKind(item.get("kind"))
        except (ValueError, TypeError):
            errors.append(
                FieldError(f"{field_prefix}.kind", "kind_not_supported", "Choose a supported kind of change.")
            )
            kind = None

        amount = _parse_money(item.get("amount"), f"{field_prefix}.amount", errors)
        frequency = _parse_frequency(item.get("frequency"), f"{field_prefix}.frequency", errors)

        if description is None or kind is None or amount is None or frequency is None:
            continue

        changes.append(
            ExpectedChange(
                entry_id=str(item.get("entry_id") or f"{prefix}-{index}"),
                description=description,
                kind=kind,
                amount=amount,
                frequency=frequency,
            )
        )

    return tuple(changes)


def _parse_statement_period(raw: Any, errors: list[FieldError]) -> date | None:
    if not isinstance(raw, str) or not raw.strip():
        errors.append(FieldError("statement_period", "period_missing", "Choose a statement period."))
        return None
    try:
        period = date.fromisoformat(raw.strip())
    except ValueError:
        errors.append(FieldError("statement_period", "period_malformed", "Use a YYYY-MM-DD date."))
        return None

    if not EARLIEST_STATEMENT_PERIOD <= period < LATEST_STATEMENT_PERIOD:
        errors.append(FieldError("statement_period", "period_out_of_range", "Choose a plausible period."))
        return None

    return period


def _parse_resilience(raw: Any, errors: list[FieldError]) -> ResilienceInput:
    if raw is None:
        return ResilienceInput()
    if not isinstance(raw, Mapping):
        errors.append(FieldError("resilience", "section_malformed", "Provide resilience information."))
        return ResilienceInput()

    def optional(key: str, *, allow_negative: bool = False) -> Decimal | None:
        if raw.get(key) is None:
            return None
        return _parse_money(raw.get(key), f"resilience.{key}", errors, allow_negative=allow_negative)

    return ResilienceInput(
        accessible_savings=optional("accessible_savings"),
        protected_reserve=optional("protected_reserve"),
        # An overdraft is reported honestly as a negative balance.
        current_account_balance=optional("current_account_balance", allow_negative=True),
        known_arrears=optional("known_arrears"),
    )


def _parse_looking_ahead(raw: Any, errors: list[FieldError]) -> LookingAheadInput:
    if raw is None:
        return LookingAheadInput()
    if not isinstance(raw, Mapping):
        errors.append(FieldError("looking_ahead", "section_malformed", "Provide looking-ahead information."))
        return LookingAheadInput()

    return LookingAheadInput(
        irregular_costs=_parse_entries(
            raw.get("irregular_costs"), "looking_ahead.irregular_costs", errors
        ),
        protected_future_provisions=_parse_entries(
            raw.get("protected_future_provisions"), "looking_ahead.protected_future_provisions", errors
        ),
        expected_changes=_parse_expected_changes(
            raw.get("expected_changes"), "looking_ahead.expected_changes", errors
        ),
    )


def validate_statement(payload: Mapping[str, Any]) -> FinancialStatement:
    """Validate a submitted financial statement, reporting every invalid field."""
    errors: list[FieldError] = []

    currency = payload.get("currency", SUPPORTED_CURRENCY)
    if currency != SUPPORTED_CURRENCY:
        errors.append(
            FieldError(
                "currency",
                "currency_not_supported",
                f"This service reports amounts in {SUPPORTED_CURRENCY}.",
            )
        )

    statement_period = _parse_statement_period(payload.get("statement_period"), errors)
    income_entries = _parse_entries(payload.get("income_entries"), "income_entries", errors)
    outgoing_entries = _parse_entries(payload.get("outgoing_entries"), "outgoing_entries", errors)
    repayment_commitments = _parse_entries(
        payload.get("repayment_commitments"), "repayment_commitments", errors
    )
    resilience = _parse_resilience(payload.get("resilience"), errors)
    looking_ahead = _parse_looking_ahead(payload.get("looking_ahead"), errors)

    if errors:
        raise StatementValidationError(errors)

    assert statement_period is not None  # guaranteed: any failure raised above

    return FinancialStatement(
        statement_period=statement_period,
        income_entries=income_entries,
        outgoing_entries=outgoing_entries,
        repayment_commitments=repayment_commitments,
        resilience=resilience,
        looking_ahead=looking_ahead,
        currency=SUPPORTED_CURRENCY,
    )


def _normalized_total(entries: Sequence[StatementEntry]) -> Decimal:
    return sum((entry.normalized_monthly_amount for entry in entries), start=Decimal("0.00"))


def preview_statement(statement: FinancialStatement) -> StatementPreview:
    """Recalculate a submitted statement without touching any confirmed snapshot."""
    # Existing repayment commitments are part of monthly outgoings; they are
    # reported separately only so the customer can see them distinctly.
    outgoings = list(statement.outgoing_entries) + list(statement.repayment_commitments)

    position = calculate_monthly_position(
        income_entries=[entry.as_money_entry() for entry in statement.income_entries],
        outgoing_entries=[entry.as_money_entry() for entry in outgoings],
    )

    resilience = calculate_resilience(
        accessible_savings=statement.resilience.accessible_savings,
        protected_reserve=statement.resilience.protected_reserve,
        current_account_balance=statement.resilience.current_account_balance,
        known_arrears=statement.resilience.known_arrears,
    )

    warnings: list[str] = []
    if statement.looking_ahead.is_empty:
        warnings.append("looking_ahead_info_missing")

    # An irregular cost that repeats an existing outgoing would be counted
    # twice if it were ever folded into monthly outgoings, so flag it for
    # review instead of silently reconciling the two.
    outgoing_descriptions = {entry.description.casefold() for entry in outgoings}
    if any(
        cost.description.casefold() in outgoing_descriptions
        for cost in statement.looking_ahead.irregular_costs
    ):
        warnings.append("possible_irregular_cost_duplication")

    return StatementPreview(
        calculation_policy_version=NORMALIZATION_POLICY_VERSION,
        position=position,
        resilience=resilience,
        normalized_monthly_repayment_commitments=_normalized_total(statement.repayment_commitments),
        # Looking-ahead provisions are reported as a separate monthly provision
        # and never alter the reported monthly headroom for this period.
        normalized_monthly_irregular_costs=_normalized_total(statement.looking_ahead.irregular_costs),
        normalized_monthly_protected_future_provisions=_normalized_total(
            statement.looking_ahead.protected_future_provisions
        ),
        expected_changes=statement.looking_ahead.expected_changes,
        warnings=tuple(warnings),
    )
