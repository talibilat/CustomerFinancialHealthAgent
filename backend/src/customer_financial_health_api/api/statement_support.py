"""Helpers shared by the statement and history routers.

These translate between the domain and the HTTP schemas, and turn domain
refusals into the one error shape the customer's form already renders.
"""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.schemas import (
    ClassificationOut,
    ConfirmedSnapshotResponse,
    EditableStatementOut,
    ExpectedChangeOut,
    LookingAheadOut,
    ResilienceOut,
    ResilienceSectionOut,
    StatementEntryOut,
    StatementSubmission,
)
from customer_financial_health_api.domain.classification import (
    TAXONOMY_VERSION,
    ClassificationOutcome,
    CustomerPreference,
    DisplayCategory,
    OutgoingTreatment,
    classify_outgoing,
    normalize_description,
)
from customer_financial_health_api.domain.statement import (
    ExpectedChange,
    FieldError,
    FinancialStatement,
    StatementEntry,
    StatementValidationError,
    validate_statement,
)
from customer_financial_health_api.persistence.repository import (
    ConfirmedSnapshotView,
    get_demo_customer,
)


def _optional_str(amount: Decimal | None) -> str | None:
    return str(amount) if amount is not None else None



def _classification_out(outcome: ClassificationOutcome) -> ClassificationOut:
    return ClassificationOut(
        display_category=outcome.display_category.value if outcome.display_category else None,
        outgoing_treatment=(
            outcome.outgoing_treatment.value if outcome.outgoing_treatment else None
        ),
        source=outcome.source.value if outcome.source else None,
        taxonomy_version=outcome.taxonomy_version,
        requires_confirmation=outcome.requires_confirmation,
        reason_code=outcome.reason_code,
    )



def _entries_out(
    entries: tuple[StatementEntry, ...],
    classifications: dict[str, ClassificationOutcome] | None = None,
) -> list[StatementEntryOut]:
    resolved = classifications or {}
    return [
        StatementEntryOut(
            entry_id=entry.entry_id,
            description=entry.description,
            original_amount=str(entry.amount),
            original_frequency=entry.frequency.value,
            normalized_monthly_amount=str(entry.normalized_monthly_amount),
            classification=(
                _classification_out(resolved[entry.entry_id])
                if entry.entry_id in resolved
                else None
            ),
        )
        for entry in entries
    ]



def _changes_out(changes: tuple[ExpectedChange, ...]) -> list[ExpectedChangeOut]:
    return [
        ExpectedChangeOut(
            entry_id=change.entry_id,
            description=change.description,
            kind=change.kind.value,
            original_amount=str(change.amount),
            original_frequency=change.frequency.value,
            normalized_monthly_amount=str(change.normalized_monthly_amount),
        )
        for change in changes
    ]



def _resolve_classifications(
    statement: FinancialStatement,
    *,
    confirmed: dict[str, ClassificationOutcome],
    preferences: tuple[CustomerPreference, ...],
) -> dict[str, ClassificationOutcome]:
    """Work out where every classifiable entry currently stands.

    A classification the customer already confirmed wins. Otherwise the
    deterministic workflow runs, which may still leave the entry unresolved.
    No provider is involved at any point.
    """
    resolved: dict[str, ClassificationOutcome] = {}
    for entry in list(statement.outgoing_entries) + list(statement.repayment_commitments):
        if entry.entry_id in confirmed:
            resolved[entry.entry_id] = confirmed[entry.entry_id]
            continue
        resolved[entry.entry_id] = classify_outgoing(entry.description, preferences=preferences)
    return resolved



def _rejected(errors: list[FieldError]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "code": "statement_invalid",
            "message": "Nothing was saved. Check the highlighted fields and try again.",
            "errors": [
                {"field": error.field, "code": error.code, "message": error.message}
                for error in errors
            ],
        },
    )



def _validated(submission: StatementSubmission) -> FinancialStatement:
    """Validate a submission, translating field errors into one safe response."""
    payload = submission.model_dump(exclude={"expected_version"})
    try:
        return validate_statement(payload)
    except StatementValidationError as invalid:
        raise _rejected(list(invalid.errors)) from invalid



def _submitted_classifications(
    submission: StatementSubmission,
) -> tuple[dict[str, ClassificationOutcome], list[tuple[str, ClassificationOutcome]]]:
    """Read the classifications the customer accepted or corrected.

    Returns the confirmed outcomes keyed by entry id, plus the subset the
    customer asked to remember as a preference. Unsupported categories and
    treatments are refused against their own field.
    """
    errors: list[FieldError] = []
    confirmed: dict[str, ClassificationOutcome] = {}
    remember: list[tuple[str, ClassificationOutcome]] = []

    sections = (
        ("outgoing_entries", submission.outgoing_entries),
        ("repayment_commitments", submission.repayment_commitments),
    )
    for prefix, entries in sections:
        for index, entry in enumerate(entries):
            if entry.classification is None:
                continue
            path = f"{prefix}.{index}.classification"

            try:
                category = DisplayCategory(entry.classification.display_category)
            except ValueError:
                errors.append(
                    FieldError(
                        f"{path}.display_category",
                        "category_not_supported",
                        "Choose one of the supported categories.",
                    )
                )
                category = None
            try:
                treatment = OutgoingTreatment(entry.classification.outgoing_treatment)
            except ValueError:
                errors.append(
                    FieldError(
                        f"{path}.outgoing_treatment",
                        "treatment_not_supported",
                        "Choose one of the supported treatments.",
                    )
                )
                treatment = None

            if category is None or treatment is None:
                continue

            entry_id = entry.entry_id or f"{prefix}-{index}"
            outcome = ClassificationOutcome(
                normalized_description=normalize_description(entry.description),
                display_category=None,
                outgoing_treatment=None,
                source=None,
                reason_code=None,
            ).confirmed_as(display_category=category, outgoing_treatment=treatment)
            confirmed[entry_id] = outcome
            if entry.classification.remember:
                remember.append((entry_id, outcome))

    if errors:
        raise _rejected(errors)

    return confirmed, remember



def _current_customer(session: Session):
    customer = get_demo_customer(session)
    if customer is None:
        raise HTTPException(status_code=404, detail="no_customer_data")
    return customer



def _snapshot_entries_out(entries) -> list[StatementEntryOut]:
    return [
        StatementEntryOut(
            entry_id=str(index),
            description=entry.description or "",
            original_amount=str(entry.original_amount),
            original_frequency=entry.original_frequency.value,
            normalized_monthly_amount=str(entry.normalized_monthly_amount),
            classification=(
                ClassificationOut(
                    display_category=(
                        entry.display_category.value if entry.display_category else None
                    ),
                    outgoing_treatment=(
                        entry.outgoing_treatment.value if entry.outgoing_treatment else None
                    ),
                    source=(
                        entry.classification_source.value if entry.classification_source else None
                    ),
                    taxonomy_version=entry.taxonomy_version or TAXONOMY_VERSION,
                    requires_confirmation=False,
                    reason_code=None,
                )
                if entry.display_category is not None
                else None
            ),
        )
        for index, entry in enumerate(entries)
    ]



def confirmed_response(snapshot: ConfirmedSnapshotView) -> ConfirmedSnapshotResponse:
    """The shared shape for a snapshot that has just been written."""
    return ConfirmedSnapshotResponse(
        snapshot_id=str(snapshot.id),
        statement_period=snapshot.statement_period,
        confirmed_at=snapshot.confirmed_at,
        calculation_policy_version=snapshot.calculation_policy_version,
        taxonomy_version=TAXONOMY_VERSION,
        normalized_monthly_income=str(snapshot.normalized_monthly_income),
        normalized_monthly_outgoings=str(snapshot.normalized_monthly_outgoings),
        monthly_headroom=str(snapshot.monthly_headroom),
        result_code=snapshot.result_code.value,
        warnings=list(snapshot.warnings),
        income_entries=_snapshot_entries_out(snapshot.income_entries),
        outgoing_entries=_snapshot_entries_out(snapshot.outgoing_entries),
        resilience=ResilienceOut(
            accessible_savings=_optional_str(snapshot.resilience.accessible_savings),
            protected_reserve=_optional_str(snapshot.resilience.protected_reserve),
            current_account_balance=_optional_str(snapshot.resilience.current_account_balance),
            known_arrears=_optional_str(snapshot.resilience.known_arrears),
            savings_above_reserve=_optional_str(snapshot.resilience.savings_above_reserve),
            reserve_gap=_optional_str(snapshot.resilience.reserve_gap),
            result_code=(
                snapshot.resilience.result_code.value if snapshot.resilience.result_code else None
            ),
            warnings=list(snapshot.resilience.warnings),
        ),
    )
