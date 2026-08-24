import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from customer_financial_health_api.domain.financial_health import (
    calculate_monthly_position,
    calculate_resilience,
    CurrentPositionResultCode,
    Frequency,
    MoneyEntry,
    MonthlyPositionResult,
    ResilienceResult,
    ResilienceResultCode,
    normalize_to_monthly,
)
from customer_financial_health_api.domain.classification import (
    TAXONOMY_VERSION,
    normalize_description,
    ClassificationOutcome,
    ClassificationSource,
    CustomerPreference,
    DisplayCategory,
    OutgoingTreatment,
)
from customer_financial_health_api.domain.statement import (
    ExpectedChange,
    ExpectedChangeKind,
    FinancialStatement,
    LookingAheadInput,
    ResilienceInput,
    StatementEntry,
)
from customer_financial_health_api.domain.repayment import (
    ScenarioMode,
    ScenarioResultCode,
    calculate_scenario,
)
from customer_financial_health_api.domain.guidance import (
    GuidanceOutcome,
    GuidanceRequestOutcome,
)
from customer_financial_health_api.persistence.models import (
    ConfirmedSnapshot,
    Customer,
    DemoState,
    EditableFinancialStatement,
    EditableStatementEntry,
    EditableStatementExpectedChange,
    CustomerClassificationPreference,
    ConfirmationIdempotencyKey,
    SnapshotIncomeEntry,
    SnapshotOutgoingEntry,
    RepaymentScenario,
    PersonalizedExplanation,
)

# Which statement section each stored entry row belongs to.
INCOME = "income"
OUTGOING = "outgoing"
REPAYMENT_COMMITMENT = "repayment_commitment"
IRREGULAR_COST = "irregular_cost"
PROTECTED_FUTURE_PROVISION = "protected_future_provision"


@dataclass(frozen=True)
class SnapshotEntryView:
    id: uuid.UUID | None
    original_amount: Decimal
    original_frequency: Frequency
    normalized_monthly_amount: Decimal
    description: str | None = None
    display_category: DisplayCategory | None = None
    outgoing_treatment: OutgoingTreatment | None = None
    classification_source: ClassificationSource | None = None
    taxonomy_version: str | None = None
    entry_key: str | None = None
    section: str | None = None


@dataclass(frozen=True)
class ConfirmedSnapshotView:
    id: uuid.UUID
    customer_id: uuid.UUID
    statement_period: date
    confirmed_at: datetime
    calculation_policy_version: str
    normalized_monthly_income: Decimal
    normalized_monthly_outgoings: Decimal
    monthly_headroom: Decimal
    result_code: CurrentPositionResultCode
    warnings: tuple[str, ...]
    income_entries: tuple[SnapshotEntryView, ...]
    outgoing_entries: tuple[SnapshotEntryView, ...]
    resilience: ResilienceResult
    supersedes_snapshot_id: uuid.UUID | None = None
    correction_reason: str | None = None


@dataclass(frozen=True)
class PersonalizedExplanationView:
    id: uuid.UUID
    customer_id: uuid.UUID
    snapshot_id: uuid.UUID
    text: str
    outcome: GuidanceRequestOutcome
    deployment: str | None
    prompt_version: str
    schema_version: str
    created_at: datetime


class StaleStatementVersion(Exception):
    """Raised when a save is built from a statement version that is no longer current."""

    def __init__(self, *, expected: int | None, current: int):
        self.expected = expected
        self.current = current
        super().__init__(f"expected version {expected}, but the stored statement is at version {current}")


@dataclass(frozen=True)
class EditableStatementView:
    id: uuid.UUID
    customer_id: uuid.UUID
    version: int
    updated_at: datetime
    statement: FinancialStatement
    # Confirmed classifications, keyed by entry id. An entry missing from this
    # mapping is unresolved and still needs the customer.
    classifications: dict[str, ClassificationOutcome] = field(default_factory=dict)


def create_customer(session: Session) -> Customer:
    customer = Customer()
    session.add(customer)
    session.flush()
    return customer


def get_demo_customer(session: Session) -> Customer | None:
    active = session.get(DemoState, 1)
    if active is not None:
        return session.get(Customer, active.active_customer_id)
    stmt = select(Customer).order_by(Customer.created_at).limit(1)
    return session.execute(stmt).scalar_one_or_none()


def get_active_demo_preset(session: Session) -> str | None:
    active = session.get(DemoState, 1)
    return active.active_preset if active is not None else None


def _entry_rows(
    entries: Sequence,
    position_amounts: Sequence[Decimal],
    row_type,
    classifications: dict[str, ClassificationOutcome] | None = None,
    entry_sections: dict[str, str] | None = None,
):
    resolved = classifications or {}
    rows = []
    for index, (entry, normalized_amount) in enumerate(zip(entries, position_amounts)):
        row = row_type(
            original_amount=entry.amount,
            original_frequency=entry.frequency.value,
            normalized_monthly_amount=normalized_amount,
            sort_order=index,
        )
        # StatementEntry carries the customer's own label; MoneyEntry does not.
        row.description = getattr(entry, "description", None)
        entry_key = getattr(entry, "entry_id", None)
        if hasattr(row, "entry_key"):
            row.entry_key = entry_key
            row.section = (entry_sections or {}).get(entry_key, OUTGOING)

        classification = resolved.get(getattr(entry, "entry_id", None))
        if classification is not None and classification.is_resolved and hasattr(row, "display_category"):
            row.display_category = classification.display_category.value
            row.outgoing_treatment = classification.outgoing_treatment.value
            row.classification_source = classification.source.value
            row.taxonomy_version = classification.taxonomy_version
        rows.append(row)
    return rows


def save_confirmed_snapshot(
    session: Session,
    *,
    customer_id: uuid.UUID,
    statement_period: date,
    confirmed_at: datetime,
    position: MonthlyPositionResult,
    income_entries: Sequence[MoneyEntry],
    outgoing_entries: Sequence[MoneyEntry],
    resilience: ResilienceResult,
    classifications: dict[str, ClassificationOutcome] | None = None,
    supersedes_snapshot_id: uuid.UUID | None = None,
    repayment_commitment_entry_ids: set[str] | None = None,
) -> ConfirmedSnapshot:
    income_normalized = [normalize_to_monthly(e.amount, e.frequency) for e in income_entries]
    outgoing_normalized = [normalize_to_monthly(e.amount, e.frequency) for e in outgoing_entries]

    snapshot = ConfirmedSnapshot(
        customer_id=customer_id,
        statement_period=statement_period,
        confirmed_at=confirmed_at,
        calculation_policy_version=position.calculation_policy_version,
        normalized_monthly_income=position.normalized_monthly_income,
        normalized_monthly_outgoings=position.normalized_monthly_outgoings,
        monthly_headroom=position.monthly_headroom,
        result_code=position.result_code.value,
        warnings=list(position.warnings),
        supersedes_snapshot_id=supersedes_snapshot_id,
        income_entries=_entry_rows(income_entries, income_normalized, SnapshotIncomeEntry),
        outgoing_entries=_entry_rows(
            outgoing_entries,
            outgoing_normalized,
            SnapshotOutgoingEntry,
            classifications,
            {
                getattr(entry, "entry_id", ""): (
                    REPAYMENT_COMMITMENT
                    if getattr(entry, "entry_id", "") in (repayment_commitment_entry_ids or set())
                    else OUTGOING
                )
                for entry in outgoing_entries
            },
        ),
        current_account_balance=resilience.current_account_balance,
        accessible_savings=resilience.accessible_savings,
        protected_reserve=resilience.protected_reserve,
        known_arrears=resilience.known_arrears,
        savings_above_reserve=resilience.savings_above_reserve,
        reserve_gap=resilience.reserve_gap,
        resilience_result_code=resilience.result_code.value if resilience.result_code else None,
        resilience_warnings=list(resilience.warnings),
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def _to_view(snapshot: ConfirmedSnapshot) -> ConfirmedSnapshotView:
    return ConfirmedSnapshotView(
        id=snapshot.id,
        customer_id=snapshot.customer_id,
        statement_period=snapshot.statement_period,
        confirmed_at=snapshot.confirmed_at,
        calculation_policy_version=snapshot.calculation_policy_version,
        normalized_monthly_income=snapshot.normalized_monthly_income,
        normalized_monthly_outgoings=snapshot.normalized_monthly_outgoings,
        monthly_headroom=snapshot.monthly_headroom,
        result_code=CurrentPositionResultCode(snapshot.result_code),
        warnings=tuple(snapshot.warnings),
        income_entries=tuple(
            SnapshotEntryView(
                id=e.id,
                original_amount=e.original_amount,
                original_frequency=Frequency(e.original_frequency),
                normalized_monthly_amount=e.normalized_monthly_amount,
                description=e.description,
            )
            for e in snapshot.income_entries
        ),
        outgoing_entries=tuple(
            SnapshotEntryView(
                id=e.id,
                original_amount=e.original_amount,
                original_frequency=Frequency(e.original_frequency),
                normalized_monthly_amount=e.normalized_monthly_amount,
                description=e.description,
                display_category=(
                    DisplayCategory(e.display_category) if e.display_category else None
                ),
                outgoing_treatment=(
                    OutgoingTreatment(e.outgoing_treatment) if e.outgoing_treatment else None
                ),
                classification_source=(
                    ClassificationSource(e.classification_source)
                    if e.classification_source
                    else None
                ),
                taxonomy_version=e.taxonomy_version,
                entry_key=e.entry_key,
                section=e.section,
            )
            for e in snapshot.outgoing_entries
        ),
        supersedes_snapshot_id=snapshot.supersedes_snapshot_id,
        correction_reason=snapshot.correction_reason,
        resilience=ResilienceResult(
            accessible_savings=snapshot.accessible_savings,
            protected_reserve=snapshot.protected_reserve,
            current_account_balance=snapshot.current_account_balance,
            known_arrears=snapshot.known_arrears,
            savings_above_reserve=snapshot.savings_above_reserve,
            reserve_gap=snapshot.reserve_gap,
            result_code=ResilienceResultCode(snapshot.resilience_result_code)
            if snapshot.resilience_result_code
            else None,
            warnings=tuple(snapshot.resilience_warnings),
        ),
    )


def get_effective_snapshot(session: Session, *, customer_id: uuid.UUID) -> ConfirmedSnapshotView | None:
    superseded_ids = select(ConfirmedSnapshot.supersedes_snapshot_id).where(
        ConfirmedSnapshot.customer_id == customer_id,
        ConfirmedSnapshot.supersedes_snapshot_id.is_not(None),
    )
    stmt = (
        select(ConfirmedSnapshot)
        .where(
            ConfirmedSnapshot.customer_id == customer_id,
            ConfirmedSnapshot.id.not_in(superseded_ids),
        )
        .order_by(ConfirmedSnapshot.statement_period.desc(), ConfirmedSnapshot.confirmed_at.desc())
        .limit(1)
    )
    snapshot = session.execute(stmt).scalar_one_or_none()
    if snapshot is None:
        return None
    return _to_view(snapshot)


class PersonalizedExplanationSnapshotNotFound(Exception):
    """The requested snapshot is absent or belongs to a different customer."""


def _personalized_explanation_view(
    row: PersonalizedExplanation,
) -> PersonalizedExplanationView:
    return PersonalizedExplanationView(
        id=row.id,
        customer_id=row.customer_id,
        snapshot_id=row.snapshot_id,
        text=row.text,
        outcome=GuidanceRequestOutcome(row.request_outcome),
        deployment=row.deployment,
        prompt_version=row.prompt_version,
        schema_version=row.schema_version,
        created_at=row.created_at,
    )


def record_personalized_explanation(
    session: Session,
    *,
    customer_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    explanation: GuidanceOutcome,
    idempotency_key: str,
    request_fingerprint: str,
    created_at: datetime,
) -> PersonalizedExplanationView:
    existing = session.execute(
        select(PersonalizedExplanation).where(
            PersonalizedExplanation.customer_id == customer_id,
            PersonalizedExplanation.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise IdempotencyConflict(
                "this idempotency key was already used for a different guidance request"
            )
        return _personalized_explanation_view(existing)

    owned_snapshot = session.execute(
        select(ConfirmedSnapshot.id).where(
            ConfirmedSnapshot.id == snapshot_id,
            ConfirmedSnapshot.customer_id == customer_id,
        )
    ).scalar_one_or_none()
    if owned_snapshot is None:
        raise PersonalizedExplanationSnapshotNotFound("no such snapshot")

    row = PersonalizedExplanation(
        customer_id=customer_id,
        snapshot_id=snapshot_id,
        text=explanation.text,
        request_outcome=explanation.outcome.value,
        deployment=explanation.deployment,
        prompt_version=explanation.prompt_version,
        schema_version=explanation.schema_version,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        created_at=created_at,
    )
    session.add(row)
    session.flush()
    return _personalized_explanation_view(row)


def get_latest_personalized_explanation(
    session: Session, *, customer_id: uuid.UUID, snapshot_id: uuid.UUID
) -> PersonalizedExplanationView | None:
    row = session.execute(
        select(PersonalizedExplanation)
        .where(
            PersonalizedExplanation.customer_id == customer_id,
            PersonalizedExplanation.snapshot_id == snapshot_id,
        )
        .order_by(
            PersonalizedExplanation.created_at.desc(),
            PersonalizedExplanation.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    return _personalized_explanation_view(row) if row is not None else None


def _entry_rows_for(
    section: str,
    entries: Sequence[StatementEntry],
    classifications: dict[str, ClassificationOutcome] | None = None,
) -> list[EditableStatementEntry]:
    resolved = classifications or {}
    rows = []
    for index, entry in enumerate(entries):
        row = EditableStatementEntry(
            section=section,
            entry_key=entry.entry_id,
            description=entry.description,
            original_amount=entry.amount,
            original_frequency=entry.frequency.value,
            sort_order=index,
        )
        classification = resolved.get(entry.entry_id)
        # Only a resolved classification is stored; an unresolved one leaves
        # the columns NULL rather than inventing a default.
        if classification is not None and classification.is_resolved:
            row.display_category = classification.display_category.value
            row.outgoing_treatment = classification.outgoing_treatment.value
            row.classification_source = classification.source.value
            row.taxonomy_version = classification.taxonomy_version
        rows.append(row)
    return rows


def save_editable_statement(
    session: Session,
    *,
    customer_id: uuid.UUID,
    statement: FinancialStatement,
    expected_version: int | None,
    classifications: dict[str, ClassificationOutcome] | None = None,
) -> EditableStatementView:
    """Create or replace the customer's editable statement for its period.

    ``expected_version`` is the version the submission was built from. Pass
    ``None`` only when creating the statement for the first time. A mismatch
    raises :class:`StaleStatementVersion` so the customer can refresh instead
    of overwriting a newer edit.
    """
    stmt = select(EditableFinancialStatement).where(
        EditableFinancialStatement.customer_id == customer_id,
        EditableFinancialStatement.statement_period == statement.statement_period,
    ).with_for_update()
    stored = session.execute(stmt).scalar_one_or_none()

    if stored is None:
        if expected_version is not None:
            raise StaleStatementVersion(expected=expected_version, current=0)
        stored = EditableFinancialStatement(
            customer_id=customer_id,
            statement_period=statement.statement_period,
            version=1,
        )
        session.add(stored)
    else:
        if expected_version != stored.version:
            raise StaleStatementVersion(expected=expected_version, current=stored.version)
        stored.version += 1

    stored.currency = statement.currency
    stored.accessible_savings = statement.resilience.accessible_savings
    stored.protected_reserve = statement.resilience.protected_reserve
    stored.current_account_balance = statement.resilience.current_account_balance
    stored.known_arrears = statement.resilience.known_arrears

    # Reported lines are replaced wholesale: the submission is the complete
    # statement, so add, change, and remove all resolve to one assignment.
    stored.entries = (
        _entry_rows_for(INCOME, statement.income_entries)
        + _entry_rows_for(OUTGOING, statement.outgoing_entries, classifications)
        + _entry_rows_for(REPAYMENT_COMMITMENT, statement.repayment_commitments, classifications)
        + _entry_rows_for(IRREGULAR_COST, statement.looking_ahead.irregular_costs)
        + _entry_rows_for(PROTECTED_FUTURE_PROVISION, statement.looking_ahead.protected_future_provisions)
    )
    stored.expected_changes = [
        EditableStatementExpectedChange(
            entry_key=change.entry_id,
            description=change.description,
            kind=change.kind.value,
            original_amount=change.amount,
            original_frequency=change.frequency.value,
            sort_order=index,
        )
        for index, change in enumerate(statement.looking_ahead.expected_changes)
    ]

    session.flush()
    return _to_editable_view(stored)


def _to_editable_view(stored: EditableFinancialStatement) -> EditableStatementView:
    def section(name: str) -> tuple[StatementEntry, ...]:
        return tuple(
            StatementEntry(
                entry_id=row.entry_key,
                description=row.description,
                amount=row.original_amount,
                frequency=Frequency(row.original_frequency),
            )
            for row in stored.entries
            if row.section == name
        )

    classifications = {
        row.entry_key: ClassificationOutcome(
            normalized_description=normalize_description(row.description),
            display_category=DisplayCategory(row.display_category),
            outgoing_treatment=OutgoingTreatment(row.outgoing_treatment),
            source=ClassificationSource(row.classification_source),
            reason_code=None,
            taxonomy_version=row.taxonomy_version,
        )
        for row in stored.entries
        if row.display_category is not None
    }

    return EditableStatementView(
        id=stored.id,
        customer_id=stored.customer_id,
        version=stored.version,
        updated_at=stored.updated_at,
        classifications=classifications,
        statement=FinancialStatement(
            statement_period=stored.statement_period,
            income_entries=section(INCOME),
            outgoing_entries=section(OUTGOING),
            repayment_commitments=section(REPAYMENT_COMMITMENT),
            resilience=ResilienceInput(
                accessible_savings=stored.accessible_savings,
                protected_reserve=stored.protected_reserve,
                current_account_balance=stored.current_account_balance,
                known_arrears=stored.known_arrears,
            ),
            looking_ahead=LookingAheadInput(
                irregular_costs=section(IRREGULAR_COST),
                protected_future_provisions=section(PROTECTED_FUTURE_PROVISION),
                expected_changes=tuple(
                    ExpectedChange(
                        entry_id=row.entry_key,
                        description=row.description,
                        kind=ExpectedChangeKind(row.kind),
                        amount=row.original_amount,
                        frequency=Frequency(row.original_frequency),
                    )
                    for row in stored.expected_changes
                ),
            ),
            currency=stored.currency,
        ),
    )


def get_editable_statement(
    session: Session, *, customer_id: uuid.UUID, statement_period: date
) -> EditableStatementView | None:
    stmt = select(EditableFinancialStatement).where(
        EditableFinancialStatement.customer_id == customer_id,
        EditableFinancialStatement.statement_period == statement_period,
    )
    stored = session.execute(stmt).scalar_one_or_none()
    if stored is None:
        return None
    return _to_editable_view(stored)


def get_customer_preferences(
    session: Session, *, customer_id: uuid.UUID
) -> tuple[CustomerPreference, ...]:
    """Every classification preference this customer has confirmed."""
    stmt = (
        select(CustomerClassificationPreference)
        .where(CustomerClassificationPreference.customer_id == customer_id)
        .order_by(CustomerClassificationPreference.normalized_description)
    )
    return tuple(
        CustomerPreference(
            normalized_description=row.normalized_description,
            display_category=DisplayCategory(row.display_category),
            outgoing_treatment=OutgoingTreatment(row.outgoing_treatment),
        )
        for row in session.execute(stmt).scalars()
    )


def save_customer_preference(
    session: Session, *, customer_id: uuid.UUID, preference: CustomerPreference
) -> None:
    """Create or update this customer's preference for one normalized phrase.

    Scoped to the customer throughout: another customer's preference for the
    same phrase is never read or written here, and the global rules are never
    touched.
    """
    stmt = select(CustomerClassificationPreference).where(
        CustomerClassificationPreference.customer_id == customer_id,
        CustomerClassificationPreference.normalized_description == preference.normalized_description,
    )
    stored = session.execute(stmt).scalar_one_or_none()

    if stored is None:
        session.add(
            CustomerClassificationPreference(
                customer_id=customer_id,
                normalized_description=preference.normalized_description,
                display_category=preference.display_category.value,
                outgoing_treatment=preference.outgoing_treatment.value,
                taxonomy_version=TAXONOMY_VERSION,
            )
        )
    else:
        stored.display_category = preference.display_category.value
        stored.outgoing_treatment = preference.outgoing_treatment.value
        stored.taxonomy_version = TAXONOMY_VERSION

    session.flush()


class IdempotencyConflict(Exception):
    """Raised when an idempotency key is reused for a materially different request."""


class UnresolvedClassifications(Exception):
    """Raised when confirmation is attempted while outgoings still need the customer."""

    def __init__(self, entry_ids: Sequence[str]):
        self.entry_ids: tuple[str, ...] = tuple(entry_ids)
        super().__init__(f"{len(self.entry_ids)} outgoing(s) still need a confirmed classification")


def _confirmation_fingerprint(
    statement: FinancialStatement, classifications: dict[str, ClassificationOutcome]
) -> str:
    """A stable digest of what is being confirmed.

    Two requests with the same reported values and the same settled meanings
    are the same confirmation; anything else is a different one.
    """
    def entries(section: Sequence[StatementEntry]) -> list:
        return [
            [entry.entry_id, entry.description, str(entry.amount), entry.frequency.value]
            for entry in section
        ]

    payload = {
        "statement_period": statement.statement_period.isoformat(),
        "currency": statement.currency,
        "income": entries(statement.income_entries),
        "outgoings": entries(statement.outgoing_entries),
        "commitments": entries(statement.repayment_commitments),
        "resilience": [
            str(statement.resilience.accessible_savings),
            str(statement.resilience.protected_reserve),
            str(statement.resilience.current_account_balance),
            str(statement.resilience.known_arrears),
        ],
        "classifications": sorted(
            [
                entry_id,
                outcome.display_category.value if outcome.display_category else None,
                outcome.outgoing_treatment.value if outcome.outgoing_treatment else None,
            ]
            for entry_id, outcome in classifications.items()
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _record_idempotent_confirmation(
    session: Session,
    *,
    customer_id: uuid.UUID,
    idempotency_key: str,
    fingerprint: str,
    snapshot_id: uuid.UUID,
) -> None:
    session.add(
        ConfirmationIdempotencyKey(
            customer_id=customer_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            snapshot_id=snapshot_id,
        )
    )
    session.flush()


def confirm_statement(
    session: Session,
    *,
    customer_id: uuid.UUID,
    statement: FinancialStatement,
    classifications: dict[str, ClassificationOutcome],
    expected_version: int,
    idempotency_key: str,
    confirmed_at: datetime,
) -> ConfirmedSnapshotView:
    """Turn the editable statement into an immutable snapshot, atomically.

    The caller owns the transaction: everything here either commits together or
    rolls back together. A repeat of the same request returns the snapshot the
    first attempt created rather than writing a second one.
    """
    fingerprint = _confirmation_fingerprint(statement, classifications)

    # A replay of an identical request returns the original result. The same key
    # carrying a different request is a conflict, not a replay.
    existing = session.execute(
        select(ConfirmationIdempotencyKey).where(
            ConfirmationIdempotencyKey.customer_id == customer_id,
            ConfirmationIdempotencyKey.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflict(
                "this idempotency key was already used for a different confirmation"
            )
        original = session.get(ConfirmedSnapshot, existing.snapshot_id)
        return _to_view(original)

    # Lock the editable statement so a concurrent confirmation cannot pass the
    # same version check, then refuse anything built from stale data.
    stored = session.execute(
        select(EditableFinancialStatement)
        .where(
            EditableFinancialStatement.customer_id == customer_id,
            EditableFinancialStatement.statement_period == statement.statement_period,
        )
        .with_for_update()
    ).scalar_one_or_none()
    current_version = stored.version if stored is not None else 0
    if current_version != expected_version:
        raise StaleStatementVersion(expected=expected_version, current=current_version)

    unresolved = [
        entry.entry_id
        for entry in list(statement.outgoing_entries) + list(statement.repayment_commitments)
        if not (
            entry.entry_id in classifications and classifications[entry.entry_id].is_resolved
        )
    ]
    if unresolved:
        raise UnresolvedClassifications(unresolved)

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

    snapshot = save_confirmed_snapshot(
        session,
        customer_id=customer_id,
        statement_period=statement.statement_period,
        confirmed_at=confirmed_at,
        position=position,
        income_entries=list(statement.income_entries),
        outgoing_entries=outgoings,
        resilience=resilience,
        classifications=classifications,
        repayment_commitment_entry_ids={
            entry.entry_id for entry in statement.repayment_commitments
        },
    )

    # Advancing the version retires the draft this snapshot was built from, so a
    # second confirmation of the same version cannot follow it.
    if stored is not None:
        stored.version += 1

    _record_idempotent_confirmation(
        session,
        customer_id=customer_id,
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
        snapshot_id=snapshot.id,
    )

    return _to_view(snapshot)


@dataclass(frozen=True)
class HistoryPage:
    snapshots: tuple[ConfirmedSnapshotView, ...]
    total: int
    limit: int
    offset: int


def _superseded_ids(customer_id: uuid.UUID):
    return select(ConfirmedSnapshot.supersedes_snapshot_id).where(
        ConfirmedSnapshot.customer_id == customer_id,
        ConfirmedSnapshot.supersedes_snapshot_id.is_not(None),
    )


def list_confirmed_history(
    session: Session, *, customer_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> HistoryPage:
    """Every confirmed snapshot this customer owns, newest period first.

    Ordering is by the period the statement describes and then by when it was
    confirmed, never by insertion order, so an out-of-order confirmation still
    reads correctly. Corrections are retained here; only the series in
    :func:`list_effective_series` collapses them.
    """
    total = session.execute(
        select(func.count())
        .select_from(ConfirmedSnapshot)
        .where(ConfirmedSnapshot.customer_id == customer_id)
    ).scalar_one()

    rows = (
        session.execute(
            select(ConfirmedSnapshot)
            .where(ConfirmedSnapshot.customer_id == customer_id)
            .order_by(
                ConfirmedSnapshot.statement_period.desc(),
                ConfirmedSnapshot.confirmed_at.desc(),
                ConfirmedSnapshot.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    return HistoryPage(
        snapshots=tuple(_to_view(row) for row in rows),
        total=total,
        limit=limit,
        offset=offset,
    )


def list_effective_series(
    session: Session, *, customer_id: uuid.UUID
) -> tuple[ConfirmedSnapshotView, ...]:
    """One snapshot per period, oldest first, for reading across time.

    A snapshot another one supersedes is excluded, so a corrected period shows
    the correction rather than both. The full record stays in history.
    """
    rows = (
        session.execute(
            select(ConfirmedSnapshot)
            .where(
                ConfirmedSnapshot.customer_id == customer_id,
                ConfirmedSnapshot.id.not_in(_superseded_ids(customer_id)),
            )
            .order_by(
                ConfirmedSnapshot.statement_period.asc(),
                ConfirmedSnapshot.confirmed_at.asc(),
            )
        )
        .scalars()
        .all()
    )

    # Defensive: if a period somehow holds more than one non-superseded record,
    # the latest confirmation represents it rather than both.
    by_period: dict[date, ConfirmedSnapshot] = {}
    for row in rows:
        by_period[row.statement_period] = row

    return tuple(_to_view(by_period[period]) for period in sorted(by_period))


MAX_CORRECTION_REASON_LENGTH = 500


class CorrectionReasonInvalid(Exception):
    """Raised when a correction is attempted without a usable reason."""


class SnapshotAlreadySuperseded(Exception):
    """Raised when correcting a snapshot another correction already replaced."""

    def __init__(self, *, snapshot_id: uuid.UUID, successor_id: uuid.UUID | None = None):
        self.snapshot_id = snapshot_id
        self.successor_id = successor_id
        super().__init__("this snapshot has already been corrected")


class SnapshotNotFound(Exception):
    """Raised when a snapshot does not exist, or is not this customer's.

    Deliberately one exception for both, so a caller cannot tell another
    customer's snapshot apart from one that never existed.
    """


def correct_snapshot(
    session: Session,
    *,
    customer_id: uuid.UUID,
    supersedes_snapshot_id: uuid.UUID,
    statement: FinancialStatement,
    classifications: dict[str, ClassificationOutcome],
    correction_reason: str,
    idempotency_key: str,
    confirmed_at: datetime,
) -> ConfirmedSnapshotView:
    """Record a correction as a new snapshot that supersedes an earlier one.

    The original is never edited or deleted. The correction keeps the period the
    original described, even when it is confirmed in a later calendar month, and
    becomes the effective snapshot for that period.
    """
    reason = (correction_reason or "").strip()
    if not reason:
        raise CorrectionReasonInvalid("a correction needs a reason")
    if len(reason) > MAX_CORRECTION_REASON_LENGTH:
        raise CorrectionReasonInvalid(
            f"a correction reason must be {MAX_CORRECTION_REASON_LENGTH} characters or fewer"
        )

    fingerprint = _confirmation_fingerprint(statement, classifications)
    existing = session.execute(
        select(ConfirmationIdempotencyKey).where(
            ConfirmationIdempotencyKey.customer_id == customer_id,
            ConfirmationIdempotencyKey.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflict(
                "this idempotency key was already used for a different correction"
            )
        return _to_view(session.get(ConfirmedSnapshot, existing.snapshot_id))

    # Lock the snapshot being corrected so two concurrent corrections cannot
    # both find it uncorrected. Ownership is checked here too: another
    # customer's snapshot is indistinguishable from one that does not exist.
    original = session.execute(
        select(ConfirmedSnapshot)
        .where(
            ConfirmedSnapshot.id == supersedes_snapshot_id,
            ConfirmedSnapshot.customer_id == customer_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if original is None:
        raise SnapshotNotFound("no such snapshot")

    successor = session.execute(
        select(ConfirmedSnapshot).where(
            ConfirmedSnapshot.supersedes_snapshot_id == supersedes_snapshot_id
        )
    ).scalar_one_or_none()
    if successor is not None:
        raise SnapshotAlreadySuperseded(
            snapshot_id=supersedes_snapshot_id, successor_id=successor.id
        )

    outgoings = list(statement.outgoing_entries) + list(statement.repayment_commitments)
    unresolved = [
        entry.entry_id
        for entry in outgoings
        if not (entry.entry_id in classifications and classifications[entry.entry_id].is_resolved)
    ]
    if unresolved:
        raise UnresolvedClassifications(unresolved)

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

    correction = save_confirmed_snapshot(
        session,
        customer_id=customer_id,
        # The period the original described, not the month it was corrected in.
        statement_period=original.statement_period,
        confirmed_at=confirmed_at,
        position=position,
        income_entries=list(statement.income_entries),
        outgoing_entries=outgoings,
        resilience=resilience,
        classifications=classifications,
        supersedes_snapshot_id=original.id,
        repayment_commitment_entry_ids={
            entry.entry_id for entry in statement.repayment_commitments
        },
    )
    correction.correction_reason = reason

    _record_idempotent_confirmation(
        session,
        customer_id=customer_id,
        idempotency_key=idempotency_key,
        fingerprint=fingerprint,
        snapshot_id=correction.id,
    )

    return _to_view(correction)


class ScenarioNotFound(Exception):
    """A scenario-owned resource is absent or belongs to another customer."""


class ScenarioBasisNotCurrent(Exception):
    """A new save tried to use a basis that has already been superseded."""


@dataclass(frozen=True)
class RepaymentScenarioView:
    id: uuid.UUID
    customer_id: uuid.UUID
    basis_snapshot_id: uuid.UUID
    basis_statement_period: date
    basis_is_superseded: bool
    mode: ScenarioMode
    selected_existing_commitment_id: uuid.UUID | None
    selected_existing_commitment_description: str | None
    proposed_repayment: Decimal
    protected_monthly_buffer: Decimal | None
    basis_monthly_headroom: Decimal
    replaced_repayment: Decimal | None
    scenario_headroom: Decimal
    buffer_shortfall: Decimal | None
    result_code: ScenarioResultCode
    warnings: tuple[str, ...]
    calculation_policy_version: str
    created_at: datetime


def _scenario_fingerprint(
    *,
    basis_snapshot_id: uuid.UUID,
    mode: ScenarioMode,
    selected_existing_commitment_id: uuid.UUID | None,
    proposed_repayment: Decimal,
    protected_monthly_buffer: Decimal | None,
) -> str:
    payload = {
        "basis_snapshot_id": str(basis_snapshot_id),
        "mode": mode.value,
        "selected_existing_commitment_id": (
            str(selected_existing_commitment_id)
            if selected_existing_commitment_id is not None
            else None
        ),
        "proposed_repayment": str(proposed_repayment),
        "protected_monthly_buffer": (
            str(protected_monthly_buffer) if protected_monthly_buffer is not None else None
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _scenario_to_view(session: Session, row: RepaymentScenario) -> RepaymentScenarioView:
    basis = session.execute(
        select(ConfirmedSnapshot).where(
            ConfirmedSnapshot.id == row.basis_snapshot_id,
            ConfirmedSnapshot.customer_id == row.customer_id,
        )
    ).scalar_one()
    basis_is_superseded = (
        session.execute(
            select(ConfirmedSnapshot.id).where(
                ConfirmedSnapshot.customer_id == row.customer_id,
                ConfirmedSnapshot.supersedes_snapshot_id == row.basis_snapshot_id,
            )
        ).first()
        is not None
    )
    commitment = (
        session.get(SnapshotOutgoingEntry, row.selected_existing_commitment_id)
        if row.selected_existing_commitment_id is not None
        else None
    )
    return RepaymentScenarioView(
        id=row.id,
        customer_id=row.customer_id,
        basis_snapshot_id=row.basis_snapshot_id,
        basis_statement_period=basis.statement_period,
        basis_is_superseded=basis_is_superseded,
        mode=ScenarioMode(row.mode),
        selected_existing_commitment_id=row.selected_existing_commitment_id,
        selected_existing_commitment_description=(commitment.description if commitment else None),
        proposed_repayment=row.proposed_repayment,
        protected_monthly_buffer=row.protected_monthly_buffer,
        basis_monthly_headroom=row.basis_monthly_headroom,
        replaced_repayment=row.replaced_repayment,
        scenario_headroom=row.scenario_headroom,
        buffer_shortfall=row.buffer_shortfall,
        result_code=ScenarioResultCode(row.result_code),
        warnings=tuple(row.warnings),
        calculation_policy_version=row.calculation_policy_version,
        created_at=row.created_at,
    )


def save_repayment_scenario(
    session: Session,
    *,
    customer_id: uuid.UUID,
    basis_snapshot_id: uuid.UUID,
    mode: ScenarioMode,
    selected_existing_commitment_id: uuid.UUID | None,
    proposed_repayment: Decimal,
    protected_monthly_buffer: Decimal | None,
    idempotency_key: str,
    created_at: datetime,
) -> RepaymentScenarioView:
    """Persist one explicit comparison without changing its immutable basis."""
    fingerprint = _scenario_fingerprint(
        basis_snapshot_id=basis_snapshot_id,
        mode=mode,
        selected_existing_commitment_id=selected_existing_commitment_id,
        proposed_repayment=proposed_repayment,
        protected_monthly_buffer=protected_monthly_buffer,
    )
    existing = session.execute(
        select(RepaymentScenario).where(
            RepaymentScenario.customer_id == customer_id,
            RepaymentScenario.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflict(
                "this idempotency key was already used for a different repayment scenario"
            )
        return _scenario_to_view(session, existing)

    basis = session.execute(
        select(ConfirmedSnapshot)
        .where(
            ConfirmedSnapshot.id == basis_snapshot_id,
            ConfirmedSnapshot.customer_id == customer_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if basis is None:
        raise ScenarioNotFound("no such basis snapshot")

    # Another request using this key may have committed while this request was
    # waiting for the basis lock. Recheck inside the serialized section so a
    # concurrent retry returns that row instead of reaching the unique
    # constraint as an internal database error.
    concurrent_retry = session.execute(
        select(RepaymentScenario).where(
            RepaymentScenario.customer_id == customer_id,
            RepaymentScenario.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if concurrent_retry is not None:
        if concurrent_retry.request_fingerprint != fingerprint:
            raise IdempotencyConflict(
                "this idempotency key was already used for a different repayment scenario"
            )
        return _scenario_to_view(session, concurrent_retry)

    successor = session.execute(
        select(ConfirmedSnapshot.id).where(
            ConfirmedSnapshot.customer_id == customer_id,
            ConfirmedSnapshot.supersedes_snapshot_id == basis_snapshot_id,
        )
    ).first()
    if successor is not None:
        raise ScenarioBasisNotCurrent("the basis snapshot has been superseded")

    commitment = None
    if mode is ScenarioMode.CHANGE_EXISTING:
        commitment = session.execute(
            select(SnapshotOutgoingEntry).where(
                SnapshotOutgoingEntry.id == selected_existing_commitment_id,
                SnapshotOutgoingEntry.snapshot_id == basis_snapshot_id,
                SnapshotOutgoingEntry.section == REPAYMENT_COMMITMENT,
            )
        ).scalar_one_or_none()
        if commitment is None:
            raise ScenarioNotFound("no such existing repayment commitment")
    elif selected_existing_commitment_id is not None:
        raise ScenarioNotFound("additional scenarios do not select an existing commitment")

    result = calculate_scenario(
        monthly_headroom=basis.monthly_headroom,
        mode=mode,
        proposed_repayment=proposed_repayment,
        replaced_repayment=(commitment.normalized_monthly_amount if commitment else None),
        protected_monthly_buffer=protected_monthly_buffer,
    )
    row = RepaymentScenario(
        customer_id=customer_id,
        basis_snapshot_id=basis_snapshot_id,
        mode=mode.value,
        selected_existing_commitment_id=(commitment.id if commitment else None),
        proposed_repayment=result.proposed_repayment,
        protected_monthly_buffer=result.protected_monthly_buffer,
        basis_monthly_headroom=result.basis_monthly_headroom,
        replaced_repayment=result.replaced_repayment,
        scenario_headroom=result.scenario_headroom,
        buffer_shortfall=result.buffer_shortfall,
        result_code=result.result_code.value,
        warnings=list(result.warnings),
        calculation_policy_version=result.calculation_policy_version,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        created_at=created_at,
    )
    session.add(row)
    session.flush()
    return _scenario_to_view(session, row)


def list_repayment_scenarios(
    session: Session, *, customer_id: uuid.UUID
) -> tuple[RepaymentScenarioView, ...]:
    rows = session.execute(
        select(RepaymentScenario)
        .where(RepaymentScenario.customer_id == customer_id)
        .order_by(RepaymentScenario.created_at.desc(), RepaymentScenario.id.desc())
    ).scalars()
    return tuple(_scenario_to_view(session, row) for row in rows)


def get_repayment_scenario(
    session: Session, *, customer_id: uuid.UUID, scenario_id: uuid.UUID
) -> RepaymentScenarioView:
    row = session.execute(
        select(RepaymentScenario).where(
            RepaymentScenario.id == scenario_id,
            RepaymentScenario.customer_id == customer_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise ScenarioNotFound("no such repayment scenario")
    return _scenario_to_view(session, row)
