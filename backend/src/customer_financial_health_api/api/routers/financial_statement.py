"""Retrieve, update, and preview the customer's editable financial statement.

None of these operations confirms a snapshot. Preview is a pure recalculation
from the submitted statement, and update replaces only the editable working
copy, so confirmed history is never touched here.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from customer_financial_health_api.api.dependencies import get_classification_provider, get_db
from customer_financial_health_api.api.schemas import (
    ClassificationOut,
    ConfirmedSnapshotResponse,
    StatementConfirmationRequest,
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
    TAXONOMY_VERSION,
    ClassificationOutcome,
    CustomerPreference,
    DisplayCategory,
    OutgoingTreatment,
    normalize_description,
)
from customer_financial_health_api.domain.suggest import ClassificationSuggestionProvider
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
    IdempotencyConflict,
    UnresolvedClassifications,
    confirm_statement,
    get_customer_preferences,
    get_active_demo_preset,
    save_customer_preference,
    StaleStatementVersion,
    get_demo_customer,
    get_editable_statement,
    save_editable_statement,
)

from customer_financial_health_api.api.statement_support import (
    _changes_out,
    _classification_out,
    _current_customer,
    _entries_out,
    _optional_str,
    _rejected,
    _resolve_classifications,
    _snapshot_entries_out,
    _submitted_classifications,
    _validated,
    confirmed_response,
)

router = APIRouter(prefix="/financial-statement", tags=["financial-statement"])


def _demo_bounded_provider(
    session: Session,
    provider: ClassificationSuggestionProvider | None,
) -> ClassificationSuggestionProvider | None:
    if get_active_demo_preset(session) == "azure_unavailable":
        return None
    return provider







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
    stored: EditableStatementView,
    preferences: tuple[CustomerPreference, ...],
    provider: ClassificationSuggestionProvider | None = None,
) -> EditableStatementResponse:
    classifications = _resolve_classifications(
        stored.statement,
        confirmed=stored.classifications,
        preferences=preferences,
        provider=provider,
    )
    return EditableStatementResponse(
        version=stored.version,
        updated_at=stored.updated_at,
        statement=_statement_out(stored.statement, classifications),
    )






@router.get("", response_model=EditableStatementResponse)
def retrieve_financial_statement(
    statement_period: date,
    session: Session = Depends(get_db),
    provider: ClassificationSuggestionProvider | None = Depends(get_classification_provider),
) -> EditableStatementResponse:
    customer = _current_customer(session)
    stored = get_editable_statement(
        session, customer_id=customer.id, statement_period=statement_period
    )
    if stored is None:
        raise HTTPException(status_code=404, detail="no_editable_statement")
    preferences = get_customer_preferences(session, customer_id=customer.id)
    bounded_provider = _demo_bounded_provider(session, provider)
    session.rollback()
    return _statement_response(
        stored,
        preferences,
        bounded_provider,
    )


@router.put("", response_model=EditableStatementResponse)
def update_financial_statement(
    submission: StatementUpdateRequest,
    session: Session = Depends(get_db),
    provider: ClassificationSuggestionProvider | None = Depends(get_classification_provider),
) -> EditableStatementResponse:
    customer = _current_customer(session)
    statement = _validated(submission)
    confirmed, remember = _submitted_classifications(submission)

    # A save that does not restate a classification must not discard it, but a
    # classification only describes the wording it was confirmed against. If the
    # customer renamed the entry, the old meaning is retired rather than carried
    # onto something they never confirmed.
    stored = get_editable_statement(
        session, customer_id=customer.id, statement_period=statement.statement_period
    )
    if stored is not None:
        submitted_descriptions = {
            entry.entry_id: normalize_description(entry.description)
            for entry in list(statement.outgoing_entries) + list(statement.repayment_commitments)
        }
        carried = {
            entry_id: outcome
            for entry_id, outcome in stored.classifications.items()
            if submitted_descriptions.get(entry_id) == outcome.normalized_description
        }
        confirmed = {**carried, **confirmed}

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
    preferences = get_customer_preferences(session, customer_id=customer.id)
    bounded_provider = _demo_bounded_provider(session, provider)
    session.rollback()
    return _statement_response(
        saved,
        preferences,
        bounded_provider,
    )


@router.post("/preview", response_model=StatementPreviewResponse)
def preview_financial_statement(
    submission: StatementSubmission,
    session: Session = Depends(get_db),
    provider: ClassificationSuggestionProvider | None = Depends(get_classification_provider),
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

    bounded_provider = _demo_bounded_provider(session, provider)
    # Preferences, the editable statement, and the active demo mode are now
    # ordinary values. End the read transaction before the optional remote
    # provider call so Azure latency never occupies a database transaction.
    session.rollback()

    classifications = _resolve_classifications(
        statement,
        confirmed=already_confirmed,
        preferences=preferences,
        provider=bounded_provider,
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



@router.post("/confirm", response_model=ConfirmedSnapshotResponse, status_code=201)
def confirm_financial_statement(
    submission: StatementConfirmationRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    session: Session = Depends(get_db),
    provider: ClassificationSuggestionProvider | None = Depends(get_classification_provider),
) -> ConfirmedSnapshotResponse:
    customer = _current_customer(session)
    statement = _validated(submission)

    if not submission.checked_information:
        raise _rejected(
            [
                FieldError(
                    "checked_information",
                    "confirmation_not_checked",
                    "Confirm that you have checked this information and believe it reflects your circumstances.",
                )
            ]
        )

    confirmed, remember = _submitted_classifications(submission)
    stored = get_editable_statement(
        session, customer_id=customer.id, statement_period=statement.statement_period
    )
    if stored is not None:
        submitted_descriptions = {
            entry.entry_id: normalize_description(entry.description)
            for entry in list(statement.outgoing_entries) + list(statement.repayment_commitments)
        }
        carried = {
            entry_id: outcome
            for entry_id, outcome in stored.classifications.items()
            if submitted_descriptions.get(entry_id) == outcome.normalized_description
        }
        confirmed = {**carried, **confirmed}

    # Anything the customer did not settle explicitly still resolves through the
    # deterministic workflow; only genuinely unresolved entries block the save.
    preferences = get_customer_preferences(session, customer_id=customer.id)
    classifications = _resolve_classifications(
        statement,
        confirmed=confirmed,
        preferences=preferences,
        provider=_demo_bounded_provider(session, provider),
    )

    for _, outcome in remember:
        save_customer_preference(
            session, customer_id=customer.id, preference=outcome.as_preference()
        )

    try:
        snapshot = confirm_statement(
            session,
            customer_id=customer.id,
            statement=statement,
            classifications=classifications,
            expected_version=submission.expected_version,
            idempotency_key=idempotency_key,
            confirmed_at=datetime.now(timezone.utc),
        )
    except StaleStatementVersion as conflict:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "statement_version_conflict",
                "message": "This statement changed. Preview it again before confirming.",
                "current_version": conflict.current,
            },
        ) from conflict
    except UnresolvedClassifications as unresolved:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "classifications_unresolved",
                "message": "Tell us what each outgoing was for before confirming.",
                "entry_ids": list(unresolved.entry_ids),
            },
        ) from unresolved
    except IdempotencyConflict as conflict:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_key_conflict",
                "message": "This confirmation reference was already used for a different statement.",
            },
        ) from conflict

    session.commit()

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
