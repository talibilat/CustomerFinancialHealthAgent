"""Retrieve, update, and preview the customer's editable financial statement.

None of these operations confirms a snapshot. Preview is a pure recalculation
from the submitted statement, and update replaces only the editable working
copy, so confirmed history is never touched here.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_db
from customer_financial_health_api.api.schemas import (
    ClassificationOut,
    EditableStatementOut,
    EditableStatementResponse,
    ExpectedChangeOut,
    LookingAheadOut,
    ResilienceOut,
    ResilienceSectionOut,
    StatementEntryOut,
    StatementPreviewResponse,
    StatementSubmission,
    StatementUpdateRequest,
)
from customer_financial_health_api.domain.classification import (
    ClassificationOutcome,
    CustomerPreference,
    DisplayCategory,
    OutgoingTreatment,
    classify_outgoing,
    normalize_description,
)
from customer_financial_health_api.domain.statement import (
    FieldError,
    ExpectedChange,
    FinancialStatement,
    StatementEntry,
    StatementValidationError,
    preview_statement,
    validate_statement,
)
from customer_financial_health_api.persistence.repository import (
    EditableStatementView,
    get_customer_preferences,
    save_customer_preference,
    StaleStatementVersion,
    get_demo_customer,
    get_editable_statement,
    save_editable_statement,
)

router = APIRouter(prefix="/financial-statement", tags=["financial-statement"])


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


def _statement_out(
    statement: FinancialStatement,
    classifications: dict[str, ClassificationOutcome] | None = None,
) -> EditableStatementOut:
    return EditableStatementOut(
        statement_period=statement.statement_period,
        currency=statement.currency,
        income_entries=_entries_out(statement.income_entries),
        outgoing_entries=_entries_out(statement.outgoing_entries, classifications),
        repayment_commitments=_entries_out(statement.repayment_commitments, classifications),
        resilience=ResilienceSectionOut(
            accessible_savings=_optional_str(statement.resilience.accessible_savings),
            protected_reserve=_optional_str(statement.resilience.protected_reserve),
            current_account_balance=_optional_str(statement.resilience.current_account_balance),
            known_arrears=_optional_str(statement.resilience.known_arrears),
        ),
        looking_ahead=LookingAheadOut(
            irregular_costs=_entries_out(statement.looking_ahead.irregular_costs),
            protected_future_provisions=_entries_out(
                statement.looking_ahead.protected_future_provisions
            ),
            expected_changes=_changes_out(statement.looking_ahead.expected_changes),
        ),
    )


def _statement_response(
    stored: EditableStatementView, preferences: tuple[CustomerPreference, ...]
) -> EditableStatementResponse:
    classifications = _resolve_classifications(
        stored.statement, confirmed=stored.classifications, preferences=preferences
    )
    return EditableStatementResponse(
        version=stored.version,
        updated_at=stored.updated_at,
        statement=_statement_out(stored.statement, classifications),
    )


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


@router.get("", response_model=EditableStatementResponse)
def retrieve_financial_statement(
    statement_period: date, session: Session = Depends(get_db)
) -> EditableStatementResponse:
    customer = _current_customer(session)
    stored = get_editable_statement(
        session, customer_id=customer.id, statement_period=statement_period
    )
    if stored is None:
        raise HTTPException(status_code=404, detail="no_editable_statement")
    return _statement_response(stored, get_customer_preferences(session, customer_id=customer.id))


@router.put("", response_model=EditableStatementResponse)
def update_financial_statement(
    submission: StatementUpdateRequest, session: Session = Depends(get_db)
) -> EditableStatementResponse:
    customer = _current_customer(session)
    statement = _validated(submission)
    confirmed, remember = _submitted_classifications(submission)

    # A correction the customer asked to remember becomes their own rule. It is
    # scoped to this customer and never edits the global rules.
    for _, outcome in remember:
        save_customer_preference(
            session, customer_id=customer.id, preference=outcome.as_preference()
        )

    try:
        saved = save_editable_statement(
            session,
            customer_id=customer.id,
            statement=statement,
            expected_version=submission.expected_version,
            classifications=confirmed,
        )
    except StaleStatementVersion as conflict:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "statement_version_conflict",
                "message": "Someone changed this statement. Refresh to see the current version.",
                "current_version": conflict.current,
            },
        ) from conflict

    session.commit()
    return _statement_response(
        saved, get_customer_preferences(session, customer_id=customer.id)
    )


@router.post("/preview", response_model=StatementPreviewResponse)
def preview_financial_statement(
    submission: StatementSubmission, session: Session = Depends(get_db)
) -> StatementPreviewResponse:
    statement = _validated(submission)
    confirmed, _ = _submitted_classifications(submission)
    preview = preview_statement(statement)

    customer = get_demo_customer(session)
    preferences = (
        get_customer_preferences(session, customer_id=customer.id) if customer else ()
    )
    stored = (
        get_editable_statement(
            session, customer_id=customer.id, statement_period=statement.statement_period
        )
        if customer
        else None
    )
    # A classification already confirmed and stored still counts as resolved,
    # even when this particular submission did not restate it.
    already_confirmed = dict(stored.classifications) if stored else {}
    already_confirmed.update(confirmed)

    classifications = _resolve_classifications(
        statement, confirmed=already_confirmed, preferences=preferences
    )
    unresolved = [
        entry_id
        for entry_id, outcome in classifications.items()
        if outcome.requires_confirmation
    ]

    return StatementPreviewResponse(
        calculation_policy_version=preview.calculation_policy_version,
        normalized_monthly_income=str(preview.position.normalized_monthly_income),
        normalized_monthly_outgoings=str(preview.position.normalized_monthly_outgoings),
        monthly_headroom=str(preview.position.monthly_headroom),
        result_code=preview.position.result_code.value,
        warnings=list(preview.position.warnings) + list(preview.warnings),
        normalized_monthly_repayment_commitments=str(
            preview.normalized_monthly_repayment_commitments
        ),
        normalized_monthly_irregular_costs=str(preview.normalized_monthly_irregular_costs),
        normalized_monthly_protected_future_provisions=str(
            preview.normalized_monthly_protected_future_provisions
        ),
        expected_changes=_changes_out(preview.expected_changes),
        resilience=ResilienceOut(
            accessible_savings=_optional_str(preview.resilience.accessible_savings),
            protected_reserve=_optional_str(preview.resilience.protected_reserve),
            current_account_balance=_optional_str(preview.resilience.current_account_balance),
            known_arrears=_optional_str(preview.resilience.known_arrears),
            savings_above_reserve=_optional_str(preview.resilience.savings_above_reserve),
            reserve_gap=_optional_str(preview.resilience.reserve_gap),
            result_code=preview.resilience.result_code.value
            if preview.resilience.result_code
            else None,
            warnings=list(preview.resilience.warnings),
        ),
        unresolved_classifications=unresolved,
        # Confirmation is withheld until every outgoing has a settled meaning.
        can_confirm=not unresolved,
    )
